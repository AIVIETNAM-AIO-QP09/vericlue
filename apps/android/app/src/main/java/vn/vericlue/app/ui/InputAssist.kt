package vn.vericlue.app.ui

/** Strict, local paste parsing. Never truncate an invalid value into a valid credential. */
object InputAssist {
    fun phone(text: String?): String? {
        val value = text?.trim()?.takeIf { it.length <= 40 } ?: return null
        if (value.any { it !in '0'..'9' && it !in " +()-" }) return null
        val compact = value.filterNot { it in " ()-" }
        val normalized = if (compact.startsWith("+84")) "0" + compact.drop(3) else compact
        return normalized.takeIf { it.length == 10 && it.startsWith('0') && it.all { ch -> ch in '0'..'9' } }
    }

    fun otp(text: String?): String? {
        val value = text?.trim()?.takeIf { it.length <= 20 } ?: return null
        val compact = value.filterNot { it == ' ' || it == '-' }
        return compact.takeIf { it.length == 6 && it.all { ch -> ch in '0'..'9' } }
    }
}
