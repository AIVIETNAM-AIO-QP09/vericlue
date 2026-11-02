package vn.vericlue.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import vn.vericlue.app.ui.InputAssist

class InputAssistTest {
    @Test fun formattedLocalAndInternationalNumbersHaveTheSameLocalValue() {
        listOf("0900 000 000", "(0900) 000-000", "+84 900 000 000").forEach {
            assertEquals("0900000000", InputAssist.phone(it))
        }
    }

    @Test fun pasteCannotSilentlyTruncateOrExtractAnUnrelatedNumber() {
        listOf(null, "", "09000000001", "9000000000", "0900000000 123", "Gọi 0900000000",
            "0900+000000", "++84900000000", "０９００００００００", "9".repeat(10000)).forEach {
            assertNull("Unexpected phone accepted: ${it?.take(30)}", InputAssist.phone(it))
        }
    }

    @Test fun otpKeepsLeadingZerosAndAcceptsVisualGrouping() {
        assertEquals("001234", InputAssist.otp(" 001 234 "))
        assertEquals("001234", InputAssist.otp("001-234"))
    }

    @Test fun otpRejectsAmbiguousOrPartialClipboardContent() {
        listOf(null, "", "12345", "1234567", "Mã 123456", "123456 654321", "12.3456", "１２３４５６").forEach {
            assertNull(InputAssist.otp(it))
        }
    }
}
