package vn.vericlue.app

import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * AGENTS.md §6 rule 3: citizens never see scores or the word "giả mạo".
 * Scans every string literal in the app source.
 */
class CitizenCopyTest {
    private val banned = listOf("giả mạo", "deepfake", "gian lận", "điểm số", "độ tin cậy", "%")
    private val literal = Regex("\"(?:[^\"\\\\]|\\\\.)*\"")

    @Test
    fun noBannedWordsInUserFacingText() {
        val root = File("src/main/java")
        assertTrue("source dir not found: ${root.absolutePath}", root.isDirectory)
        val hits = root.walk().filter { it.extension == "kt" }.flatMap { file ->
            file.readLines().withIndex().flatMap { (i, line) ->
                literal.findAll(line).map { it.value }
                    .filter { lit -> banned.any { lit.contains(it, ignoreCase = true) } }
                    .map { "${file.name}:${i + 1} $it" }
            }
        }.toList()
        assertTrue("Banned citizen-facing words:\n" + hits.joinToString("\n"), hits.isEmpty())
    }
}
