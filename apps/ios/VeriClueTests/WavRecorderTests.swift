import AVFoundation
import Foundation
import Testing
@testable import VeriClue

@MainActor
struct WavRecorderTests {
    private func integer(_ data: Data, at offset: Int, bytes: Int) -> Int {
        (0..<bytes).reduce(0) { $0 | Int(data[offset + $1]) << (8 * $1) }
    }

    @Test func canonicalHeaderIsExactly44BytesAndLittleEndian() throws {
        let pcm = Data([0x00, 0x80, 0xff, 0x7f, 0, 0])
        let wav = try WavPCM.encode(pcm)
        #expect(wav.count == 44 + pcm.count)
        #expect(String(decoding: wav[0..<4], as: UTF8.self) == "RIFF")
        #expect(String(decoding: wav[8..<12], as: UTF8.self) == "WAVE")
        #expect(integer(wav, at: 4, bytes: 4) == 36 + pcm.count)
        #expect(integer(wav, at: 16, bytes: 4) == 16)
        #expect(integer(wav, at: 20, bytes: 2) == 1)
        #expect(integer(wav, at: 22, bytes: 2) == 1)
        #expect(integer(wav, at: 24, bytes: 4) == 16_000)
        #expect(integer(wav, at: 28, bytes: 4) == 32_000)
        #expect(integer(wav, at: 32, bytes: 2) == 2)
        #expect(integer(wav, at: 34, bytes: 2) == 16)
        #expect(String(decoding: wav[36..<40], as: UTF8.self) == "data")
        #expect(integer(wav, at: 40, bytes: 4) == pcm.count)
        #expect(wav.dropFirst(44) == pcm)
        #expect(throws: WavError.empty) { try WavPCM.encode(Data()) }
        #expect(throws: WavError.empty) { try WavPCM.encode(Data([1])) }
        #expect(throws: WavError.empty) { try WavPCM.encode(Data(repeating: 1, count: 256_002)) }
    }

    private func synthetic(rate: Double = 48_000, channels: AVAudioChannelCount = 2, silence: Bool = false) throws -> AVAudioPCMBuffer {
        let format = try #require(AVAudioFormat(standardFormatWithSampleRate: rate, channels: channels))
        let buffer = try #require(AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 4800))
        buffer.frameLength = 4800
        let samples = try #require(buffer.floatChannelData)
        for channel in 0..<Int(channels) {
            for i in 0..<4800 { samples[channel][i] = silence ? 0 : Float(sin(Double(i) * 2 * .pi * 440 / rate) * 0.2) }
        }
        return buffer
    }

    @Test func encodedWavCanBeDecodedByAVAudioFile() throws {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("ios05-synthetic-\(UUID().uuidString).wav")
        defer { try? FileManager.default.removeItem(at: url) }
        let bytes = try WavPCM.encode(Data(repeating: 32, count: 3200))
        try bytes.write(to: url, options: .withoutOverwriting)
        let file = try AVAudioFile(forReading: url, commonFormat: .pcmFormatInt16, interleaved: false)
        #expect(file.fileFormat.sampleRate == 16_000 && file.fileFormat.channelCount == 1)
        #expect(file.length == 1600)
        let buffer = try #require(AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: 1600))
        try file.read(into: buffer)
        #expect(buffer.frameLength == 1600)
        #expect(buffer.int16ChannelData?[0][0] == 0x2020)
    }

    @Test func convertsStereo48kToMono16kInt16AndCapsAtEightSeconds() throws {
        let input = try synthetic()
        let collector = try AudioPCMCollector(input: input.format)
        var meter: WavMeter?
        for i in 0..<90 {
            meter = collector.consume(input, at: AVAudioTime(hostTime: AVAudioTime.hostTime(forSeconds: 100 + Double(i) / 10)))
        }
        #expect(meter?.limitReached == true)
        let result = try collector.finish()
        #expect(result.data.count == 256_044)
        #expect(result.seconds == 8)
        #expect(abs(result.firstHostSeconds - 100) < 0.001)
        #expect(result.peakRms > 0.05)
        #expect(integer(result.data, at: 24, bytes: 4) == 16_000)
        #expect(integer(result.data, at: 22, bytes: 2) == 1)
        #expect(integer(result.data, at: 34, bytes: 2) == 16)
        #expect(throws: WavError.cancelled) { try collector.finish() }
    }

    @Test func zeroPcmAndMissingInputAreNotExportableVoice() throws {
        let input = try synthetic(silence: true)
        let collector = try AudioPCMCollector(input: input.format)
        for i in 0..<5 {
            _ = collector.consume(input, at: AVAudioTime(hostTime: AVAudioTime.hostTime(forSeconds: 100 + Double(i) / 10)))
        }
        #expect(throws: WavError.empty) { try collector.finish() }
        let empty = try AudioPCMCollector(input: input.format)
        #expect(throws: WavError.empty) { try empty.finish() }
    }

    @Test func invalidOrDiscontinuousAudioClockFailsClosed() throws {
        let input = try synthetic()
        let invalid = try AudioPCMCollector(input: input.format)
        let noHost = AVAudioTime(sampleTime: 0, atRate: 48_000)
        #expect(invalid.consume(input, at: noHost).failure == .invalidClock)
        #expect(throws: WavError.invalidClock) { try invalid.finish() }
        let gap = try AudioPCMCollector(input: input.format)
        _ = gap.consume(input, at: AVAudioTime(hostTime: AVAudioTime.hostTime(forSeconds: 100)))
        #expect(gap.consume(input, at: AVAudioTime(hostTime: AVAudioTime.hostTime(forSeconds: 101))).failure == .invalidClock)
        #expect(throws: WavError.invalidClock) { try gap.finish() }
    }

    @Test func offsetUsesFirstAudioSampleNotButtonTime() throws {
        #expect(try WavPCM.offsetMs(audioHost: 500.1234, videoHost: 500) == 123)
        #expect(try WavPCM.offsetMs(audioHost: 500, videoHost: 500) == 0)
        for audio in [499.9, 504, Double.nan, Double.infinity] {
            #expect(throws: WavError.invalidClock) { try WavPCM.offsetMs(audioHost: audio, videoHost: 500) }
        }
    }
}
