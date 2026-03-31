// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CursorSettings",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    targets: [
        .target(
            name: "CursorSettings",
            path: "Sources/CursorSettings",
            resources: [
                .process("Resources")
            ]
        )
    ]
)
