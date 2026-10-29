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

        XCTAssertTrue(app.staticTexts["Ngân hàng Mẫu"].waitForExistence(timeout: 15))

        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = "IOS-01 Launch"
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
