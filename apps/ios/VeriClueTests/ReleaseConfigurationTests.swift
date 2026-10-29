import Foundation
import Testing
@testable import VeriClue

@MainActor
struct ReleaseConfigurationTests {
    @Test func signingFlagCannotBeHardcodedInSourcePlists() throws {
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
        for path in ["VeriClue/Info.plist", "Config/Release-Info.plist"] {
            let data = try Data(contentsOf: root.appendingPathComponent(path))
            let info = try #require(try PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any])
            #expect(info["SIGNED_MEDIA"] as? String == "$(SIGNED_MEDIA)")
        }
    }
    @Test func releaseEndpointRequiresHTTPSAndNoEmbeddedCredentials() {
        for raw in [nil, "", "https://<cloudflared-domain>/", "$(API_BASE_URL)",
                    "http://192.168.1.12:8001/", "file:///tmp/api", "https://user:secret@demo.invalid/",
                    "https://demo.invalid/?token=secret", "https://demo.invalid/#fragment", " https://demo.invalid/"] {
            #expect(APIEndpointPolicy.baseURL(raw, requiresHTTPS: true) == nil)
        }
        #expect(APIEndpointPolicy.baseURL("https://demo.invalid/api/", requiresHTTPS: true)?.absoluteString == "https://demo.invalid/api/")
    }

    @Test func debugStillAllowsLANAndReleaseDoesNot() {
        let raw = "http://192.168.1.12:8001/"
        #expect(APIEndpointPolicy.baseURL(raw, requiresHTTPS: false) != nil)
        #expect(APIEndpointPolicy.baseURL(raw, requiresHTTPS: true) == nil)
    }

    @Test func bundledTransportConfigurationMatchesBuild() {
        let bundle = Bundle.main // Hosted app, not the .xctest bundle.
        let ats = bundle.object(forInfoDictionaryKey: "NSAppTransportSecurity") as? [String: Any]
        #if DEBUG
        #expect(ats?["NSAllowsLocalNetworking"] as? Bool == true)
        #else
        #expect(ats == nil)
        #expect(bundle.object(forInfoDictionaryKey: "NSLocalNetworkUsageDescription") == nil)
        #expect(DemoFlow().useLiveAPI)
        #endif
    }
}
