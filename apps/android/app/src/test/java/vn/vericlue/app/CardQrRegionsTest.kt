package vn.vericlue.app

import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.capture.CardFrameRect
import vn.vericlue.app.capture.cardQrRetryRegions
import vn.vericlue.app.capture.uniqueCardQr

class CardQrRegionsTest {
    @Test fun missingFullCardCandidateStillGetsTwoOverlappingNativePixelRegions() {
        val regions = cardQrRetryRegions(1000, 630, emptyList())
        assertEquals(listOf(CardFrameRect(0, 0, 650, 630), CardFrameRect(350, 0, 1000, 630)), regions)
        // The QR can be on either side or across the center; never assume its printed position.
        for (qr in listOf(CardFrameRect(10, 10, 240, 240), CardFrameRect(760, 10, 990, 240),
            CardFrameRect(400, 190, 600, 390))) assertTrue(regions.any { contains(it, qr) })
    }

    @Test fun fallbackStaysInsideVisibleCardAndKeepsFullHeightAtDifferentAspects() {
        for ((width, height) in listOf(1079 to 680, 680 to 429, 600 to 950)) {
            val regions = cardQrRetryRegions(width, height, emptyList())
            assertEquals(2, regions.size)
            assertEquals(0, regions.first().left)
            assertEquals(width, regions.last().right)
            assertTrue(regions.first().right > regions.last().left)
            for (region in regions) {
                assertEquals(0, region.top)
                assertEquals(height, region.bottom)
                assertTrue(region.left >= 0 && region.right <= width && region.width in 1 until width)
            }
        }
    }

    @Test fun knownCandidatesUseTightPaddedRegionsAndNeverMoreThanTwoRetries() {
        assertEquals(listOf(CardFrameRect(60, 60, 340, 340), CardFrameRect(788, 28, 852, 92)),
            cardQrRetryRegions(1000, 630, listOf(CardFrameRect(800, 40, 840, 80),
                CardFrameRect(100, 100, 300, 300), CardFrameRect(500, 100, 520, 120))))
        assertEquals(listOf(CardFrameRect(0, 0, 120, 120)),
            cardQrRetryRegions(1000, 630, listOf(CardFrameRect(-20, -10, 100, 100))))
    }

    @Test fun degenerateCandidatesCannotDisableNoCandidateRecovery() {
        assertEquals(cardQrRetryRegions(1000, 630, emptyList()),
            cardQrRetryRegions(1000, 630, listOf(CardFrameRect(1001, 0, 1100, 200), CardFrameRect(20, 20, 20, 40))))
        assertEquals(2, cardQrRetryRegions(1000, 630, listOf(CardFrameRect(20, 20, 20, 40))).size)
    }

    @Test fun conflictingValidPayloadsFromFullImageAndRoiNeverChooseTheFirstCard() {
        val first = "001095012345||Nguyễn Văn A|01011995|Nam|Hà Nội|15072021"
        val other = first.replace("001095012345", "001095012346")
        val fullImage = listOf(first)
        val firstRoi = listOf(first, "https://example.com")
        val secondRoi = listOf(other)
        assertEquals(first, uniqueCardQr(fullImage + firstRoi))
        assertNull(uniqueCardQr(fullImage + firstRoi + secondRoi))
        assertNull(uniqueCardQr(firstRoi + secondRoi))
    }

    private fun contains(outer: CardFrameRect, inner: CardFrameRect) =
        outer.left <= inner.left && outer.top <= inner.top && outer.right >= inner.right && outer.bottom >= inner.bottom
}
