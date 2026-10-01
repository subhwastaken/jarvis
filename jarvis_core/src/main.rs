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

fn ok_resp<T: Serialize>(data: T) -> serde_json::Result<String> {
    serde_json::to_string(&Response { status: "ok".to_string(), data })
}

fn err_resp(msg: &str) -> serde_json::Result<String> {
    serde_json::to_string(&Response {
        status: "error".to_string(),
        data: serde_json::json!({ "message": msg }),
    })
}

// ---------------------------------------------------------------------------
// System Telemetry
// ---------------------------------------------------------------------------

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
        let (mut free, mut active, mut inactive, mut speculative) = (0u64, 0u64, 0u64, 0u64);
        for line in text.lines() {
            let parts: Vec<&str> = line.split(':').collect();
            if parts.len() == 2 {
                let key = parts[0].trim();
                let val_str = parts[1].trim().trim_end_matches('.');
                if let Ok(val) = val_str.parse::<u64>() {
                    match key {
                        "Pages free"        => free = val,
                        "Pages active"      => active = val,
                        "Pages inactive"    => inactive = val,
                        "Pages speculative" => speculative = val,
                        _ => {}
                    }
                }
            }
        }
        let total_free_mb = ((free + speculative) * 4) / 1024;
        let used_mb = ((active + inactive) * 4) / 1024;
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

fn get_current_volume() -> i64 {
    let script = "output volume of (get volume settings)";
    if let Ok(out) = Command::new("osascript").arg("-e").arg(script).output() {
        if let Ok(v) = String::from_utf8_lossy(&out.stdout).trim().parse::<i64>() {
            return v;
        }
    }
    50
}

// ---------------------------------------------------------------------------
// Action Handlers
// ---------------------------------------------------------------------------

fn handle_open_app(payload: &serde_json::Value) -> serde_json::Result<String> {
    let app = payload.get("app").and_then(|v| v.as_str()).unwrap_or("");
    if app.is_empty() { return err_resp("No app name provided"); }
    let _ = Command::new("open").arg("-a").arg(app).spawn();
    ok_resp(serde_json::json!({ "action": "open_app", "app": app, "success": true }))
}

fn handle_quit_app(payload: &serde_json::Value) -> serde_json::Result<String> {
    let app = payload.get("app").and_then(|v| v.as_str()).unwrap_or("");
    if app.is_empty() { return err_resp("No app name provided"); }
    let script = format!("tell application \"{}\" to quit", app);
    let _ = Command::new("osascript").arg("-e").arg(&script).output();
    let _ = Command::new("pkill").arg("-f").arg(app).output();
    ok_resp(serde_json::json!({ "action": "quit_app", "app": app, "success": true }))
}

fn handle_set_volume(payload: &serde_json::Value) -> serde_json::Result<String> {
    let level = payload.get("level").and_then(|v| v.as_i64()).unwrap_or(50).max(0).min(100);
    let _ = Command::new("osascript").arg("-e").arg(format!("set volume output volume {}", level)).output();
    ok_resp(serde_json::json!({ "action": "set_volume", "level": level, "success": true }))
}

fn handle_adjust_volume(payload: &serde_json::Value) -> serde_json::Result<String> {
    let delta = payload.get("delta").and_then(|v| v.as_i64()).unwrap_or(10);
    let current = get_current_volume();
    let new_level = (current + delta).max(0).min(100);
    let _ = Command::new("osascript").arg("-e").arg(format!("set volume output volume {}", new_level)).output();
    ok_resp(serde_json::json!({ "action": "adjust_volume", "old": current, "new": new_level }))
}

fn handle_mute_volume(payload: &serde_json::Value) -> serde_json::Result<String> {
    let mute = payload.get("mute").and_then(|v| v.as_bool()).unwrap_or(true);
    let val = if mute { "true" } else { "false" };
    let _ = Command::new("osascript").arg("-e").arg(format!("set volume output muted {}", val)).output();
    ok_resp(serde_json::json!({ "action": "mute_volume", "muted": mute, "success": true }))
}

fn handle_media_action(payload: &serde_json::Value) -> serde_json::Result<String> {
    let action = payload.get("action").and_then(|v| v.as_str()).unwrap_or("play");
    for app in &["Spotify", "Music"] {
        let check = format!("application \"{}\" is running", app);
        if let Ok(out) = Command::new("osascript").arg("-e").arg(&check).output() {
            if String::from_utf8_lossy(&out.stdout).trim() == "true" {
                let cmd = match action {
                    "pause" | "stop" => format!("tell application \"{}\" to pause", app),
                    "next"           => format!("tell application \"{}\" to next track", app),
                    "previous"       => format!("tell application \"{}\" to previous track", app),
                    _                => format!("tell application \"{}\" to play", app),
                };
                let _ = Command::new("osascript").arg("-e").arg(&cmd).output();
                return ok_resp(serde_json::json!({ "action": action, "app": app, "success": true }));
            }
        }
    }
    let _ = Command::new("open").arg("-a").arg("Music").spawn();
    ok_resp(serde_json::json!({ "action": action, "app": "Music", "success": true }))
}

fn handle_dark_mode(payload: &serde_json::Value) -> serde_json::Result<String> {
    let mode = payload.get("mode").and_then(|v| v.as_str()).unwrap_or("toggle");
    let script = match mode {
        "on"  => "tell application \"System Events\" to tell appearance preferences to set dark mode to true".to_string(),
        "off" => "tell application \"System Events\" to tell appearance preferences to set dark mode to false".to_string(),
        _     => "tell application \"System Events\" to tell appearance preferences to set dark mode to not dark mode".to_string(),
    };
    let _ = Command::new("osascript").arg("-e").arg(&script).output();
    ok_resp(serde_json::json!({ "action": "dark_mode", "mode": mode, "success": true }))
}

fn handle_screenshot() -> serde_json::Result<String> {
    use std::time::{SystemTime, UNIX_EPOCH};
    let ts = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs();
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    let path = format!("{}/Desktop/Screenshot-{}.png", home, ts);
    let _ = Command::new("screencapture").arg("-x").arg(&path).output();
    ok_resp(serde_json::json!({ "action": "screenshot", "path": path, "success": true }))
}

fn handle_notify(payload: &serde_json::Value) -> serde_json::Result<String> {
    let title   = payload.get("title").and_then(|v| v.as_str()).unwrap_or("JARVIS");
    let message = payload.get("message").and_then(|v| v.as_str()).unwrap_or("Notification");
    let subtitle = payload.get("subtitle").and_then(|v| v.as_str()).unwrap_or("");
    let script = format!(
        "display notification \"{}\" with title \"{}\" subtitle \"{}\"",
        message, title, subtitle
    );
    let _ = Command::new("osascript").arg("-e").arg(&script).output();
    ok_resp(serde_json::json!({ "action": "notify", "success": true }))
}

fn handle_get_volume() -> serde_json::Result<String> {
    let level = get_current_volume();
    let muted = Command::new("osascript").arg("-e").arg("output muted of (get volume settings)").output()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_lowercase() == "true")
        .unwrap_or(false);
    ok_resp(serde_json::json!({ "volume": level, "muted": muted }))
}

// ---------------------------------------------------------------------------
// Client handler
// ---------------------------------------------------------------------------

fn handle_client(stream: UnixStream, start_time: Instant) {
    let mut reader = BufReader::new(match stream.try_clone() { Ok(s) => s, Err(_) => return });
    let mut writer = stream;
    let mut line = String::new();
    if reader.read_line(&mut line).is_ok() && !line.trim().is_empty() {
        let req: Result<Request, _> = serde_json::from_str(line.trim());
        let response_json = match req {
            Ok(r) => match r.action.as_str() {
                "ping" => ok_resp(serde_json::json!({
                    "daemon": "jarvis_core", "language": "rust",
                    "version": "0.2.0", "uptime_secs": start_time.elapsed().as_secs()
                })),
                "telemetry" => {
                    let telem = Telemetry {
                        uptime_secs: start_time.elapsed().as_secs(),
                        ram_usage: get_ram_usage(), battery: get_battery_status(),
                        load_avg: get_load_average(), active_app: get_active_app(),
                    };
                    ok_resp(serde_json::to_value(telem).unwrap_or_default())
                }
                "lock_screen"   => { let _ = Command::new("pmset").arg("displaysleepnow").output(); ok_resp(serde_json::json!({ "success": true })) }
                "sleep_display" => { let _ = Command::new("pmset").arg("displaysleepnow").output(); ok_resp(serde_json::json!({ "success": true })) }
                "sleep_system"  => { let _ = Command::new("pmset").arg("sleepnow").spawn(); ok_resp(serde_json::json!({ "success": true })) }
                "empty_trash"   => { let _ = Command::new("osascript").arg("-e").arg("tell application \"Finder\" to empty trash").output(); ok_resp(serde_json::json!({ "success": true })) }
                "screenshot"    => handle_screenshot(),
                "dark_mode"     => handle_dark_mode(&r.payload),
                "get_volume"    => handle_get_volume(),
                "set_volume"    => handle_set_volume(&r.payload),
                "adjust_volume" => handle_adjust_volume(&r.payload),
                "mute_volume"   => handle_mute_volume(&r.payload),
                "media"         => handle_media_action(&r.payload),
                "open_app"      => handle_open_app(&r.payload),
                "quit_app"      => handle_quit_app(&r.payload),
                "notify"        => handle_notify(&r.payload),
                other           => err_resp(&format!("Unknown action '{}'", other)),
            },
            Err(e) => err_resp(&format!("Invalid JSON: {}", e)),
        };
        if let Ok(resp) = response_json {
            let _ = writeln!(writer, "{}", resp);
            let _ = writer.flush();
        }
    }
}

fn main() {
    println!("⚡ J.A.R.V.I.S. Core Rust Daemon v0.2.0 starting...");
    let start_time = Instant::now();
    if Path::new(SOCKET_PATH).exists() { let _ = fs::remove_file(SOCKET_PATH); }
    let listener = match UnixListener::bind(SOCKET_PATH) {
        Ok(l) => l,
        Err(e) => { eprintln!("Socket bind error: {}", e); std::process::exit(1); }
    };
    println!("⚡ Listening at {} — 18 actions supported", SOCKET_PATH);
    listener.set_nonblocking(true).unwrap();
    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();
    let mut last_heartbeat = Instant::now();
    while r.load(Ordering::SeqCst) {
        match listener.accept() {
            Ok((stream, _)) => handle_client(stream, start_time),
            Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => std::thread::sleep(Duration::from_millis(50)),
            Err(e) => { eprintln!("Accept error: {}", e); std::thread::sleep(Duration::from_millis(100)); }
        }
        if last_heartbeat.elapsed() >= Duration::from_secs(60) {
            println!("⚡ [Pulse] uptime: {}s", start_time.elapsed().as_secs());
            last_heartbeat = Instant::now();
        }
    }
    if Path::new(SOCKET_PATH).exists() { let _ = fs::remove_file(SOCKET_PATH); }
}
