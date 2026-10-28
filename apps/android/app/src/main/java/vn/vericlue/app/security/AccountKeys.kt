package vn.vericlue.app.security

import java.util.UUID

/** Key lifecycle is separate from receipts; no private key leaves the Keystore. */
interface AccountKeys {
    fun exists(alias: String): Boolean
    fun open(alias: String, create: Boolean): MediaSigner
    fun delete(alias: String)
}

object KeyAliases {
    fun valid(alias: String) = alias.matches(Regex("vericlue\\.media\\.[A-Za-z0-9._-]{1,100}"))
    fun fresh() = "vericlue.media.${UUID.randomUUID()}"
}

class AndroidAccountKeys : AccountKeys {
    override fun exists(alias: String) = AndroidMediaSigner.exists(alias)
    override fun open(alias: String, create: Boolean): MediaSigner = AndroidMediaSigner(alias, create)
    override fun delete(alias: String) = AndroidMediaSigner.delete(alias)
}
