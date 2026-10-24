package vn.vericlue.app

import java.io.File
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.vericlue.app.capture.CamProbe
import vn.vericlue.app.data.api.Challenge
import vn.vericlue.app.data.api.ColorEvent
import vn.vericlue.app.data.api.ColorStep
import vn.vericlue.app.data.api.CreateSessionResponse
import vn.vericlue.app.data.api.FinalizeResponse
import vn.vericlue.app.data.api.FrameTime
import vn.vericlue.app.data.api.Signals
import vn.vericlue.app.data.api.StepAck
import vn.vericlue.app.data.api.VoiceResponse

/**
 * AGENTS.md §6 rule 1: the app's models must match packages/contracts. Reads the JSON Schema
 * (the source of truth) and checks every hand-written model against it.
 */
class ContractTest {
    private val defs: JsonObject = Json.parseToJsonElement(
        File("../../../packages/contracts/schemas/session.schema.json").readText(),
    ).jsonObject["\$defs"]!!.jsonObject

    private fun props(def: JsonObject): Set<String> = def["properties"]?.jsonObject?.keys.orEmpty()
    private fun required(def: JsonObject): Set<String> =
        def["required"]?.jsonArray?.map { it.jsonPrimitive.content }?.toSet().orEmpty()

    /** Server → app: read only declared fields, and require only what the contract requires. */
    private fun checkResponse(name: String, serializer: KSerializer<*>) {
        val def = defs[name]!!.jsonObject
        val d = serializer.descriptor
        val names = (0 until d.elementsCount).map(d::getElementName)
        val unknown = names - props(def)
        assertTrue("$name: fields not in the contract: $unknown", unknown.isEmpty())
        val mustHave = (0 until d.elementsCount).filterNot(d::isElementOptional).map(d::getElementName)
        val notRequired = mustHave - required(def)
        assertTrue("$name: app requires fields the contract does not: $notRequired", notRequired.isEmpty())
    }

    /** App → server: send every required field and nothing undeclared. */
    private fun checkRequest(def: JsonObject, label: String, serializer: KSerializer<*>) {
        val d = serializer.descriptor
        val names = (0 until d.elementsCount).map(d::getElementName).toSet()
        val missing = required(def) - names
        val unknown = names - props(def)
        assertTrue("$label: missing required fields $missing", missing.isEmpty())
        assertTrue("$label: fields not in the contract: $unknown", unknown.isEmpty())
    }

    @Test
    fun responsesMatchTheContract() {
        checkResponse("ColorStep", ColorStep.serializer())
        checkResponse("Challenge", Challenge.serializer())
        checkResponse("CreateSessionResponse", CreateSessionResponse.serializer())
        checkResponse("StepAck", StepAck.serializer())
        checkResponse("FinalizeResponse", FinalizeResponse.serializer())
        checkResponse("VoiceResponse", VoiceResponse.serializer())
    }

    @Test
    fun signalsMatchTheContract() {
        val signals = defs["Signals"]!!.jsonObject
        checkRequest(signals, "Signals", Signals.serializer())
        val p = signals["properties"]!!.jsonObject
        checkRequest(p["color_events"]!!.jsonObject["items"]!!.jsonObject, "ColorEvent", ColorEvent.serializer())
        checkRequest(p["frame_times"]!!.jsonObject["items"]!!.jsonObject, "FrameTime", FrameTime.serializer())
        checkRequest(p["camprobe"]!!.jsonObject, "CamProbe", CamProbe.serializer())
    }
}
