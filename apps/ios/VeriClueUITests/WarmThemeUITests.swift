import XCTest

final class WarmThemeUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }

    @MainActor func testLightThemeScreensAndTargets() throws { try inspect(theme: "light", large: false) }
    @MainActor func testDarkThemeScreensAndTargets() throws { try inspect(theme: "dark", large: false) }
    @MainActor func testLightAccessibilityTextAndReducedMotion() throws { try inspect(theme: "light", large: true) }
    @MainActor func testDarkAccessibilityTextAndReducedMotion() throws { try inspect(theme: "dark", large: true) }

    @MainActor
    private func inspect(theme: String, large: Bool) throws {
        let app = XCUIApplication()
        app.launchArguments += ["--vc-theme", theme, "--vc-navigation-trace"]
        if large { app.launchArguments += ["--vc-text-size", "accessibility3", "--vc-reduce-motion"] }
        app.launch()
        let gallery = app.buttons["debug-gallery-button"]
        XCTAssertTrue(gallery.waitForExistence(timeout: 15))
        XCTAssertTrue(gallery.isHittable)
        XCTAssertGreaterThanOrEqual(gallery.frame.height, 44)
        gallery.tap()
        XCTAssertTrue(app.staticTexts["debug-gallery-title"].waitForExistence(timeout: 15))

        let routes = [
            ("Đăng nhập / Đăng ký", "Mở tài khoản\ntrong 2 phút", "welcome"),
            ("Điều khoản và đồng ý", "Điều khoản và đồng ý", "terms"),
            ("OTP", "Nhập mã xác nhận", "otp"),
            ("Xem lại hai mặt CCCD", "Kiểm tra hai mặt CCCD", "card-review"),
            ("Kiểm tra thông tin", "Kiểm tra thông tin", "confirm"),
            ("Thành công", "Xác minh thành công", "success")
        ]
        for (label, heading, name) in routes {
            let target = app.buttons[label]
            bringIntoView(target, app: app)
            target.tap()
            XCTAssertTrue(app.staticTexts[heading].waitForExistence(timeout: 15), name)
            // Accessibility existence can precede the final navigation render.
            // Wait only in the test runner, never in capture/timeline code.
            Thread.sleep(forTimeInterval: 1)
            if name == "welcome" {
                let register = app.buttons["Đăng ký"]
                XCTAssertTrue(register.isHittable)
                XCTAssertGreaterThanOrEqual(register.frame.height, 56)
                XCTAssertGreaterThanOrEqual(register.frame.minX, 0)
                XCTAssertLessThanOrEqual(register.frame.maxX, app.frame.maxX)
            }
            if name == "success" {
                XCTAssertTrue(app.otherElements["vc-brand-emblem"].exists)
                XCTAssertTrue(app.staticTexts["Dữ liệu mẫu"].exists)
            }
            let shot = XCTAttachment(screenshot: app.screenshot())
            shot.name = "warm-\(theme)-\(large ? "AX3-reduced" : "default")-\(name)"
            shot.lifetime = .keepAlways
            add(shot)
            if large && name == "otp" {
                let code = app.descendants(matching: .any).matching(identifier: "otp-code").firstMatch
                bringIntoView(code, app: app)
                XCTAssertEqual(code.value as? String, "654321")
                for _ in 0..<6 { app.buttons["keypad-delete"].tap() }
                for digit in "111111" { app.buttons["keypad-digit-\(digit)"].tap() }
                bringIntoView(code, app: app)
                XCTAssertEqual(code.value as? String, "111111")
                app.buttons["Xác nhận"].tap()
                let error = app.staticTexts["Mã chưa đúng. Bạn còn 4 lần thử."]
                bringIntoView(error, app: app)
                XCTAssertTrue(error.isHittable)
                // Editing after a rejected code must work without submitting automatically.
                app.buttons["keypad-digit-6"].tap()
                for digit in "54321" { app.buttons["keypad-digit-\(digit)"].tap() }
                bringIntoView(code, app: app)
                XCTAssertEqual(code.value as? String, "654321")
                let entered = XCTAttachment(screenshot: app.screenshot())
                entered.name = "warm-\(theme)-AX3-otp-manual-input"
                entered.lifetime = .keepAlways
                add(entered)
                XCTAssertTrue(app.buttons["Xác nhận"].isEnabled)
                XCTAssertFalse(app.staticTexts["Chụp mặt trước CCCD"].exists)
                app.buttons["Xác nhận"].tap()
                XCTAssertTrue(app.staticTexts["Chụp mặt trước CCCD"].waitForExistence(timeout: 15))
                app.navigationBars.buttons.element(boundBy: 0).tap()
                XCTAssertTrue(code.waitForExistence(timeout: 15))
                XCTAssertEqual(code.value as? String, "654321")
            }
            if large && name == "confirm" {
                for value in ["NGUYỄN VĂN A", "001 095 012 345", "01/01/1995", "Nam",
                              "Số 1 Đại Cồ Việt, Hai Bà Trưng, Hà Nội"] {
                    let field = app.staticTexts[value]
                    bringIntoView(field, app: app)
                    XCTAssertTrue(field.isHittable)
                    XCTAssertGreaterThanOrEqual(field.frame.minX, 0)
                    XCTAssertLessThanOrEqual(field.frame.maxX, app.frame.maxX)
                }
                XCTAssertTrue(app.buttons["Thông tin đúng"].isHittable)
                XCTAssertTrue(app.buttons["Sửa thông tin"].isHittable)
                let scrolled = XCTAttachment(screenshot: app.screenshot())
                scrolled.name = "warm-\(theme)-AX3-confirm-end"
                scrolled.lifetime = .keepAlways
                add(scrolled)
            }
            if name == "terms" {
                // Repeat the actual native Back/push cycle, not a fallback tap.
                for _ in 0..<2 {
                    app.navigationBars.buttons.element(boundBy: 0).tap()
                    XCTAssertTrue(app.navigationBars["Xem tất cả màn"].waitForExistence(timeout: 10))
                    bringIntoView(app.buttons[label], app: app)
                    app.buttons[label].tap()
                    XCTAssertTrue(app.staticTexts[heading].waitForExistence(timeout: 15))
                }
            }
            let back = app.navigationBars.buttons.element(boundBy: 0)
            XCTAssertTrue(back.exists && back.isHittable)
            back.tap()
            // Assert the current navigation bar, not a heading that may be outside
            // the restored scroll viewport. One Back tap only; never retry it.
            XCTAssertTrue(app.navigationBars["Xem tất cả màn"].waitForExistence(timeout: 10))
        }
    }

    @MainActor
    private func bringIntoView(_ target: XCUIElement, app: XCUIApplication,
                               file: StaticString = #filePath, line: UInt = #line) {
        let scroll = app.scrollViews.firstMatch
        guard scroll.waitForExistence(timeout: 10) else {
            XCTFail("Expected a scrollable screen before looking for \(target)", file: file, line: line)
            return
        }
        func bottom() -> CGFloat {
            if app.buttons["Thông tin đúng"].exists { return min(scroll.frame.maxY, app.buttons["Thông tin đúng"].frame.minY) }
            if app.buttons["keypad-done"].exists { return min(scroll.frame.maxY, app.buttons["Xác nhận"].frame.minY) }
            return scroll.frame.maxY
        }
        func fullyVisible() -> Bool {
            target.isHittable && target.frame.minY >= scroll.frame.minY + 8 && target.frame.maxY <= bottom() - 8
        }
        for _ in 0..<35 {
            if fullyVisible() { break }
            let up = !target.exists || target.frame.maxY > bottom() - 8
            // ScrollView's AX frame can extend behind a safeAreaInset footer.
            // Keep the gesture in its visible content, never on the fixed keypad.
            let top = scroll.frame.minY + 8
            let height = max(1, bottom() - 8 - top)
            let x = scroll.frame.midX
            let origin = app.coordinate(withNormalizedOffset: .zero)
            origin.withOffset(CGVector(dx: x, dy: top + height * (up ? 0.8 : 0.2)))
                .press(forDuration: 0.05, thenDragTo:
                    origin.withOffset(CGVector(dx: x, dy: top + height * (up ? 0.2 : 0.8))))
        }
        XCTAssertTrue(fullyVisible(), "Gallery target must be fully visible: \(target)", file: file, line: line)
    }
}
