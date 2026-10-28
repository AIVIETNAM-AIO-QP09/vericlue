import Foundation

struct MultipartBody {
    let boundary = "VeriClue-" + UUID().uuidString
    private var bytes = Data()

    mutating func field(_ name: String, _ value: String) {
        appendHeader(name: name, filename: nil, contentType: nil)
        bytes.append(Data(value.utf8))
        bytes.append(Data("\r\n".utf8))
    }

    mutating func file(_ name: String, filename: String, contentType: String, data: Data) {
        appendHeader(name: name, filename: filename, contentType: contentType)
        bytes.append(data)
        bytes.append(Data("\r\n".utf8))
    }

    var data: Data { bytes + Data("--\(boundary)--\r\n".utf8) }
    var contentType: String { "multipart/form-data; boundary=\(boundary)" }

    private mutating func appendHeader(name: String, filename: String?, contentType: String?) {
        // Only caller-owned constants are used as field names/filenames, never user input.
        var header = "--\(boundary)\r\nContent-Disposition: form-data; name=\"\(name)\""
        if let filename { header += "; filename=\"\(filename)\"" }
        header += "\r\n"
        if let contentType { header += "Content-Type: \(contentType)\r\n" }
        bytes.append(Data((header + "\r\n").utf8))
    }
}
