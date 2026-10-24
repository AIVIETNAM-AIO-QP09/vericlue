//
//  VeriClueUITestsLaunchTests.swift
//  VeriClueUITests
//
//  Created by NÂUQ on 25/10/26.
//

import XCTest

final class VeriClueUITestsLaunchTests: XCTestCase {

    override class var runsForEachTargetApplicationUIConfiguration: Bool {
        true
    }

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testLaunch() throws {
        let app = XCUIApplication()
        app.launch()

        let galleryButton = app.buttons["debug-gallery-button"]
        XCTAssertTrue(galleryButton.waitForExistence(timeout: 15))
        galleryButton.tap()
        XCTAssertTrue(app.staticTexts["debug-gallery-title"].waitForExistence(timeout: 15))

        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = "IOS-01 Debug Gallery"
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
