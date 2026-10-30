package vn.vericlue.app

import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.ui.components.ovalRect

class CameraGeometryTest {
    @Test fun headGuideGivesMoreRoomWithoutChangingOtherScreens() {
        val regular = ovalRect(375f, 500f, 1f)
        val turning = ovalRect(375f, 500f, 1f, fitHeight = true)
        assertTrue(turning.width > regular.width)
        assertTrue(turning.right <= 375f && turning.bottom <= 500f)
    }

    @Test fun headGuideFitsTheSpaceLeftByLargeText() {
        for (height in listOf(150f, 200f, 400f)) {
            val oval = ovalRect(375f, height, 1f, fitHeight = true)
            assertTrue(oval.top >= 0 && oval.bottom <= height)
            assertTrue(oval.left >= 0 && oval.right <= 375f)
        }
    }
}
