//
//  ContentView.swift
//  VeriClue
//
//  Created by NÂUQ on 25/10/26.
//

import SwiftUI

struct ContentView: View {
    @Environment(\.dynamicTypeSize) private var systemTypeSize

    var body: some View {
        VcThemeRoot {
            AppNavigationView()
        }
        #if DEBUG
        // Presentation-only overrides for repeatable Simulator screenshots. No flow/API shortcuts.
        .preferredColorScheme(ThemePreviewConfiguration.current.colorScheme)
        .dynamicTypeSize(ThemePreviewConfiguration.current.typeSize ?? systemTypeSize)
        .environment(\.vcReduceMotionOverride, ThemePreviewConfiguration.current.reduceMotion)
        #endif
    }
}

#Preview {
    ContentView()
}
