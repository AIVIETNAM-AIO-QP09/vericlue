//
//  VeriClueUITests.swift
//  VeriClueUITests
//
//  Created by NÂUQ on 25/10/26.
//

import XCTest

final class VeriClueUITests: XCTestCase {

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.

        // In UI tests it is usually best to stop immediately when a failure occurs.
        continueAfterFailure = false

        // In UI tests it’s important to set the initial state - such as interface orientation - required for your tests before they run. The setUp method is a good place to do this.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    @MainActor
    func testLaunchShowsMockBank() throws {
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.staticTexts["Ngân hàng Mẫu"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["Mở tài khoản"].exists)
    }

    @MainActor
    func testTermsRequiresExplicitConsentAndContinuesDirectlyToPhone() throws {
        let app = XCUIApplication()
        app.launch()
        app.buttons["Mở tài khoản"].tap()
        XCTAssertTrue(app.buttons["Đăng ký"].waitForExistence(timeout: 15))
        app.buttons["Đăng ký"].tap()
        let next = app.buttons["terms-continue"]
        XCTAssertTrue(next.waitForExistence(timeout: 15))
        XCTAssertFalse(next.isEnabled)
        let read = app.buttons["terms-read-end"]
        scrollTermsFullyIntoView(read, app: app)
        read.tap()
        XCTAssertFalse(next.isEnabled)
        let agreement = app.buttons["terms-agreement"]
        scrollTermsFullyIntoView(agreement, app: app)
        XCTAssertTrue(agreement.isEnabled)
        XCTAssertEqual(agreement.value as? String, "Chưa đồng ý")
        agreement.tap()
        XCTAssertEqual(agreement.value as? String, "Đã đồng ý")
        XCTAssertFalse(next.isEnabled) // Acknowledging the terms alone is not enough.
        let required = app.buttons["consent-choice-0"]
        scrollTermsFullyIntoView(required, app: app)
        XCTAssertEqual(required.value as? String, "Chưa chọn")
        required.tap()
        XCTAssertEqual(required.value as? String, "Đã chọn")
        XCTAssertTrue(next.isEnabled)
        next.tap()
        XCTAssertTrue(app.staticTexts["Số điện thoại của bạn"].waitForExistence(timeout: 15))
    }

    @MainActor
    private func scrollTermsFullyIntoView(_ element: XCUIElement, app: XCUIApplication,
                                         file: StaticString = #filePath, line: UInt = #line) {
        let scroll = app.scrollViews["terms-scroll"]
        XCTAssertTrue(scroll.exists, file: file, line: line)
        let next = app.buttons["terms-continue"]
        func fullyVisible() -> Bool {
            let top = scroll.frame.minY + 8
            let bottom = min(scroll.frame.maxY, next.frame.minY) - 8
            return element.isHittable && element.frame.minY >= top && element.frame.maxY <= bottom
        }
        for _ in 0..<20 {
            if fullyVisible() { break }
            let moveUp = element.frame.maxY > min(scroll.frame.maxY, next.frame.minY) - 8
            let start = scroll.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: moveUp ? 0.7 : 0.4))
            let end = scroll.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: moveUp ? 0.45 : 0.65))
            start.press(forDuration: 0.05, thenDragTo: end)
        }
        // isHittable alone permits a mostly clipped row; its default tap can hit the fixed footer.
        XCTAssertTrue(fullyVisible(), "Control must be fully above the fixed action area", file: file, line: line)
    }

    @MainActor
    func testDebugGalleryOpens() throws {
        let app = XCUIApplication()
        app.launch()
        let galleryButton = app.buttons["debug-gallery-button"]
        XCTAssertTrue(galleryButton.waitForExistence(timeout: 15))
        XCTAssertTrue(galleryButton.isHittable)
        // The visible button padding must be tappable, not only its text glyphs.
        galleryButton.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.15)).tap()
        XCTAssertTrue(app.staticTexts["debug-gallery-title"].waitForExistence(timeout: 15))
        XCTAssertTrue(app.staticTexts["Lỗi và gián đoạn"].exists)

        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = "IOS-01 Debug Gallery"
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
