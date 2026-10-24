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
    func testDebugGalleryOpens() throws {
        let app = XCUIApplication()
        app.launch()
        let galleryButton = app.buttons["debug-gallery-button"]
        XCTAssertTrue(galleryButton.waitForExistence(timeout: 15))
        galleryButton.tap()
        XCTAssertTrue(app.staticTexts["debug-gallery-title"].waitForExistence(timeout: 15))
        XCTAssertTrue(app.staticTexts["Lỗi và gián đoạn"].exists)
    }
}
