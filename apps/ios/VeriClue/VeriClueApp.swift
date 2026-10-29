//
//  VeriClueApp.swift
//  VeriClue
//
//  Created by NÂUQ on 25/10/26.
//

import SwiftUI

@main
struct VeriClueApp: App {
    init() {
        #if DEBUG
        let missingFonts = VcFont.missingPostScriptNames
        assert(missingFonts.isEmpty, "Thiếu font: \(missingFonts.joined(separator: ", "))")
        #endif
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
