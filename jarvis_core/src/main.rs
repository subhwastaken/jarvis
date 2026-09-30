use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::Path;
use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

const SOCKET_PATH: &str = "/tmp/jarvis.sock";

#[derive(Deserialize, Debug)]
struct Request {
    action: String,
    #[serde(default)]
    payload: serde_json::Value,
}

#[derive(Serialize, Debug)]
struct Telemetry {
    uptime_secs: u64,
    ram_usage: String,
    battery: String,
    load_avg: String,
    active_app: String,
}

#[derive(Serialize, Debug)]
struct Response<T: Serialize> {
    status: String,
    data: T,
}

fn get_active_app() -> String {
    let script = "tell application \"System Events\" to get name of first application process whose frontmost is true";
    if let Ok(out) = Command::new("osascript").arg("-e").arg(script).output() {
        if out.status.success() {
            return String::from_utf8_lossy(&out.stdout).trim().to_string();
        }
    }
    "Unknown".to_string()
}

fn get_battery_status() -> String {
    if let Ok(out) = Command::new("pmset").arg("-g").arg("batt").output() {
        let text = String::from_utf8_lossy(&out.stdout);
        for line in text.lines() {
            if line.contains('%') {
                if let Some(start) = line.find('\t') {
                    return line[start + 1..].trim().to_string();
                }
                return line.trim().to_string();
            }
        }
    }
    "Battery info unavailable".to_string()
}

fn get_ram_usage() -> String {
    if let Ok(out) = Command::new("vm_stat").output() {
        let text = String::from_utf8_lossy(&out.stdout);
        let mut free = 0u64;
        let mut active = 0u64;
        let mut inactive = 0u64;
        let mut speculative = 0u64;

        for line in text.lines() {
            let parts: Vec<&str> = line.split(':').collect();
            if parts.len() == 2 {
                let key = parts[0].trim();
                let val_str = parts[1].trim().trim_end_matches('.');
                if let Ok(val) = val_str.parse::<u64>() {
                    match key {
                        "Pages free" => free = val,
                        "Pages active" => active = val,
                        "Pages inactive" => inactive = val,
                        "Pages speculative" => speculative = val,
                        _ => {}
                    }
                }
            }
        }
        let page_size_kb = 4u64; // macOS standard page size
        let total_free_mb = ((free + speculative) * page_size_kb) / 1024;
        let used_mb = ((active + inactive) * page_size_kb) / 1024;
        return format!("{used_mb} MB used / {total_free_mb} MB free");
    }
    "RAM info unavailable".to_string()
}

fn get_load_average() -> String {
    if let Ok(out) = Command::new("sysctl").arg("-n").arg("vm.loadavg").output() {
        let raw = String::from_utf8_lossy(&out.stdout);
        return raw.trim().trim_matches('{').trim_matches('}').trim().to_string();
    }
    "N/A".to_string()
}

fn handle_client(stream: UnixStream, start_time: Instant) {
    let mut reader = BufReader::new(match stream.try_clone() {
        Ok(s) => s,
        Err(_) => return,
    });
    let mut writer = stream;

    let mut line = String::new();
    if reader.read_line(&mut line).is_ok() && !line.trim().is_empty() {
        let req: Result<Request, _> = serde_json::from_str(line.trim());
        let response_json = match req {
            Ok(r) => match r.action.as_str() {
                "ping" => serde_json::to_string(&Response {
                    status: "ok".to_string(),
                    data: serde_json::json!({
                        "daemon": "jarvis_core",
                        "language": "rust",
                        "version": "0.1.0",
                        "uptime_secs": start_time.elapsed().as_secs(),
                    }),
                }),
                "telemetry" => {
                    let telem = Telemetry {
                        uptime_secs: start_time.elapsed().as_secs(),
                        ram_usage: get_ram_usage(),
                        battery: get_battery_status(),
                        load_avg: get_load_average(),
                        active_app: get_active_app(),
                    };
                    serde_json::to_string(&Response {
                        status: "ok".to_string(),
                        data: serde_json::to_value(telem).unwrap_or_default(),
                    })
                }
                "lock_screen" => {
                    let _ = Command::new("pmset").arg("displaysleepnow").output();
                    serde_json::to_string(&Response {
                        status: "ok".to_string(),
                        data: serde_json::json!({"action": "lock_screen", "success": true}),
                    })
                }
                "empty_trash" => {
                    let script = "tell application \"Finder\" to empty trash";
                    let _ = Command::new("osascript").arg("-e").arg(script).output();
                    serde_json::to_string(&Response {
                        status: "ok".to_string(),
                        data: serde_json::json!({"action": "empty_trash", "success": true}),
                    })
                }
                _ => serde_json::to_string(&Response {
                    status: "error".to_string(),
                    data: serde_json::json!({"message": format!("Unknown action '{}'", r.action)}),
                }),
            },
            Err(e) => serde_json::to_string(&Response {
                status: "error".to_string(),
                data: serde_json::json!({"message": format!("Invalid JSON request: {}", e)}),
            }),
        };

        if let Ok(resp) = response_json {
            let _ = writeln!(writer, "{}", resp);
            let _ = writer.flush();
        }
    }
}

fn main() {
    println!("⚡ Starting J.A.R.V.I.S. Core (Rust Always-On Daemon)...");
    let start_time = Instant::now();

    // Clean up stale socket file if it exists
    if Path::new(SOCKET_PATH).exists() {
        let _ = fs::remove_file(SOCKET_PATH);
    }

    let listener = match UnixListener::bind(SOCKET_PATH) {
        Ok(l) => l,
        Err(e) => {
            eprintln!("Failed to bind Unix socket at {}: {}", SOCKET_PATH, e);
            std::process::exit(1);
        }
    };

    println!("⚡ Socket listening at {}", SOCKET_PATH);

    // Set up non-blocking mode or standard accept loop with signal awareness
    listener.set_nonblocking(true).expect("Cannot set non-blocking");

    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();

    // Background monitor loop
    let mut last_heartbeat = Instant::now();

    while r.load(Ordering::SeqCst) {
        match listener.accept() {
            Ok((stream, _)) => {
                handle_client(stream, start_time);
            }
            Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                std::thread::sleep(Duration::from_millis(50));
            }
            Err(e) => {
                eprintln!("Accept error: {}", e);
                std::thread::sleep(Duration::from_millis(100));
            }
        }

        // Periodic 60s health pulse
        if last_heartbeat.elapsed() >= Duration::from_secs(60) {
            println!("⚡ [Pulse] Daemon uptime: {}s | Socket healthy", start_time.elapsed().as_secs());
            last_heartbeat = Instant::now();
        }
    }

    if Path::new(SOCKET_PATH).exists() {
        let _ = fs::remove_file(SOCKET_PATH);
    }
}
