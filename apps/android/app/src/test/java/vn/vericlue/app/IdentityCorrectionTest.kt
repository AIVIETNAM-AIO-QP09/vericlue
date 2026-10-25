package vn.vericlue.app

import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.data.api.IdCardFields
import vn.vericlue.app.flow.FlowRules

class IdentityCorrectionTest {
    @Test fun missingOcrNumberDoesNotBecomeSampleData() {
        val fields = IdCardFields(fullName = "An")
        assertEquals("", FlowRules.cccdFrom(fields).idNumber)
        assertEquals("An", FlowRules.cccdFrom(fields).fullName)
    }

    @Test fun correctedIdNumberIsSentToServer() {
        val server = IdCardFields(fullName = "An", idNumber = "001099012345")
        val shown = listOf("An", "001 099 012 345", "01/01/1995", "Nam", "Hà Nội")
        val edited = shown.toMutableList().apply { this[1] = "001 099 012 346" }
        assertEquals("001099012346", FlowRules.confirmedFields(server, shown, edited).idNumber)
    }

    @Test fun incompleteAndImpossibleDatesCannotBeConfirmed() {
        val values = listOf("An", "001 099 012 345", "01/01/1995", "Nam", "Hà Nội")
        assertTrue(FlowRules.validIdentityValues(values))
        assertFalse(FlowRules.validIdentityValues(values.toMutableList().apply { this[1] = "" }))
        assertFalse(FlowRules.validIdentityValues(values.toMutableList().apply { this[2] = "31/02/1995" }))
    }
}
