import SwiftUI
import WebKit

// MARK: - Native SwiftUI Siri Orb (Pure Swift / SwiftUI implementation)
public struct NativeSiriOrb: View {
    @State private var rotation: Double = 0
    var size: CGFloat = 24
    var animationDuration: Double = 16.0
    
    // Apple Intelligence palette
    var bg: Color = Color(red: 0.95, green: 0.95, blue: 1.0)
    var c1: Color = Color(red: 1.0, green: 0.16, blue: 0.52)  // Hot pink / magenta
    var c2: Color = Color(red: 0.0, green: 0.85, blue: 1.0)   // Electric Cyan
    var c3: Color = Color(red: 0.6, green: 0.2, blue: 1.0)    // Purple / Indigo
    
    public init(size: CGFloat = 24, animationDuration: Double = 16.0) {
        self.size = size
        self.animationDuration = animationDuration
    }
    
    public var body: some View {
        ZStack {
            // Fluid multi-conic mesh layer
            AngularGradient(
                gradient: Gradient(colors: [c1, c2, c3, c1, c2, c3, c1]),
                center: .center,
                angle: .degrees(rotation)
            )
            .blur(radius: size * 0.06)
            .contrast(1.3)
            
            // Secondary counter-rotating flow
            AngularGradient(
                gradient: Gradient(colors: [c2.opacity(0.8), c3.opacity(0.8), c1.opacity(0.8), c2.opacity(0.8)]),
                center: .topLeading,
                angle: .degrees(-rotation * 1.5)
            )
            .blendMode(.plusLighter)
            .blur(radius: size * 0.08)
            
            // Subtle specular glass highlight
            RadialGradient(
                gradient: Gradient(colors: [Color.white.opacity(0.4), Color.clear]),
                center: .topLeading,
                startRadius: 0,
                endRadius: size * 0.7
            )
            .blendMode(.overlay)
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .shadow(color: c2.opacity(0.4), radius: 6, x: 0, y: 0)
        .shadow(color: c1.opacity(0.3), radius: 10, x: 0, y: 0)
        .onAppear {
            withAnimation(.linear(duration: animationDuration).repeatForever(autoreverses: false)) {
                rotation = 360
            }
        }
    }
}

// MARK: - Native Dynamic Island Capsule (SwiftUI)
public struct DynamicIslandPillView: View {
    @State public var assistantState: String = "Ready"
    @State public var assistantDetail: String = "Tap or Right Alt to talk"
    public var onPillTapped: () -> Void = {}
    
    public var body: some View {
        HStack(spacing: 8) {
            // 1. Left: Siri Orb
            NativeSiriOrb(size: 24, animationDuration: assistantState == "Listening" ? 3.5 : 12.0)
                .scaleEffect(assistantState == "Listening" ? 1.15 : 1.0)
                .animation(.spring(response: 0.35, dampingFraction: 0.65), value: assistantState)
            
            // 2. Center: Assistant Status & Transcript
            VStack(alignment: .leading, spacing: 1) {
                Text(statusTitle)
                    .font(.system(size: 11, weight: .semibold, design: .rounded))
                    .foregroundColor(statusColor)
                    .lineLimit(1)
                
                Text(assistantDetail)
                    .font(.system(size: 9, weight: .regular))
                    .foregroundColor(Color(white: 0.65))
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            
            // 3. Right: Hardware Camera Lens Cutout & Equalizer Activity Dots
            HStack(spacing: 6) {
                // Hardware Camera lens
                ZStack {
                    Circle()
                        .fill(
                            RadialGradient(
                                gradient: Gradient(colors: [Color(red: 0.1, green: 0.15, blue: 0.22), Color(red: 0.02, green: 0.04, blue: 0.08)]),
                                center: .topLeading,
                                startRadius: 0,
                                endRadius: 7
                            )
                        )
                        .frame(width: 13, height: 13)
                        .overlay(
                            Circle()
                                .stroke(Color.black, lineWidth: 0.5)
                        )
                    
                    // Lens reflection
                    Circle()
                        .fill(
                            RadialGradient(
                                gradient: Gradient(colors: [Color.cyan.opacity(0.9), Color.blue.opacity(0.5)]),
                                center: .center,
                                startRadius: 0,
                                endRadius: 3
                            )
                        )
                        .frame(width: 4.5, height: 4.5)
                }
                
                // 4 Activity Dots
                HStack(spacing: 2) {
                    ForEach(0..<4) { index in
                        Capsule()
                            .fill(statusColor)
                            .frame(width: 2.5, height: barHeight(for: index))
                            .animation(
                                assistantState == "Listening" || assistantState == "Speaking"
                                    ? .easeInOut(duration: 0.4).repeatForever().delay(Double(index) * 0.12)
                                    : .default,
                                value: assistantState
                            )
                    }
                }
            }
        }
        .padding(.horizontal, 10)
        .frame(width: assistantState == "Listening" ? 285 : 265, height: 38)
        .background(Color.black)
        .clipShape(Capsule())
        .overlay(
            Capsule()
                .stroke(Color.white.opacity(0.18), lineWidth: 0.5)
        )
        .shadow(color: Color.black.opacity(0.85), radius: 15, x: 0, y: 10)
        .shadow(color: statusGlowColor, radius: 12, x: 0, y: 0)
        .contentShape(Capsule())
        .onTapGesture {
            onPillTapped()
        }
    }
    
    private var statusTitle: String {
        switch assistantState.lowercased() {
        case let s where s.contains("listen"): return "LISTENING"
        case let s where s.contains("think"):  return "THINKING"
        case let s where s.contains("speak"):  return "SPEAKING"
        default: return "NIKO"
        }
    }
    
    private var statusColor: Color {
        switch assistantState.lowercased() {
        case let s where s.contains("listen"): return Color(red: 0.22, green: 0.74, blue: 0.97)
        case let s where s.contains("think"):  return Color(red: 0.75, green: 0.52, blue: 0.99)
        case let s where s.contains("speak"):  return Color(red: 0.2, green: 0.83, blue: 0.6)
        default: return .white
        }
    }
    
    private var statusGlowColor: Color {
        switch assistantState.lowercased() {
        case let s where s.contains("listen"): return Color.cyan.opacity(0.35)
        case let s where s.contains("think"):  return Color.purple.opacity(0.35)
        case let s where s.contains("speak"):  return Color.green.opacity(0.3)
        default: return Color.clear
        }
    }
    
    private func barHeight(for index: Int) -> CGFloat {
        if assistantState == "Listening" || assistantState == "Speaking" {
            return CGFloat([9, 13, 7, 11][index])
        }
        return 6
    }
}
