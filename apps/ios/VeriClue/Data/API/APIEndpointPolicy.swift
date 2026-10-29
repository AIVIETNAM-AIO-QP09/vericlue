import Foundation

enum APIEndpointPolicy {
    static func baseURL(_ raw: String?, requiresHTTPS: Bool) -> URL? {
        guard let raw, !raw.isEmpty,
              !raw.contains(where: \.isWhitespace),
              !raw.contains("<"), !raw.contains(">"), !raw.contains("$("),
              let components = URLComponents(string: raw),
              let host = components.host, !host.isEmpty,
              components.user == nil, components.password == nil,
              components.query == nil, components.fragment == nil,
              let scheme = components.scheme?.lowercased(),
              requiresHTTPS ? scheme == "https" : ["http", "https"].contains(scheme),
              let url = components.url else { return nil }
        return url
    }

    static var requiresHTTPS: Bool {
        #if DEBUG
        false
        #else
        true
        #endif
    }
}
