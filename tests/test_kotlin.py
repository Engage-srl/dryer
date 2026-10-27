from pathlib import Path

from dryer.discover import iter_source_files, language_of
from dryer.extract import entries_in_source
from dryer.model import Entry
from dryer.scan import find_duplicates, scan_files


def write_source(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def pairs(root: Path):
    files = sorted(path for path in root.rglob("*") if path.is_file())
    entries, warnings = scan_files(files, root, min_lines=1, min_nodes=1)
    assert warnings == []
    return find_duplicates(entries, threshold=0.99)


def forms(source: str, file: str) -> list[Entry]:
    entries, warning = entries_in_source("kotlin", source, file, file)
    assert warning is None
    return entries


def _function(body: str, name: str = "alpha") -> str:
    return f"package demo\n\nfun {name}(xs: List<Int>, a: String?): Any {{\n{body}\n}}\n"


def _score(left: str, right: str) -> float:
    found = find_duplicates(forms(left, "a.kt") + forms(right, "b.kt"), threshold=0.0)
    assert len(found) == 1
    return found[0].score


def test_kotlin_matches_renamed_locals(tmp_path):
    write_source(
        tmp_path,
        "left.kt",
        "fun alpha(xs: List<Int>): List<Int> {\n    val ys = filter(xs, odd)\n    return map(ys, inc)\n}\n",
    )
    write_source(
        tmp_path,
        "right.kt",
        "fun beta(items: List<Int>): List<Int> {\n    val kept = filter(items, even)\n    return map(kept, dec)\n}\n",
    )
    found = pairs(tmp_path)
    assert len(found) == 1
    assert found[0].language == "kotlin"
    assert found[0].score == 1.0


def test_kotlin_member_calls_keep_their_names():
    filtered = _function("    return xs.filter { it > 0 }.size")
    mapped = _function("    return xs.map { it > 0 }.size", "beta")
    counted = _function("    return ys.filter { it > 1 }.count", "beta")
    assert _score(filtered, mapped) < 0.99
    assert _score(filtered, counted) == 1.0


def test_kotlin_safe_call_is_part_of_the_shape():
    safe = _function("    val t = a?.trim()\n    return t")
    plain = _function("    val t = a.trim()\n    return t", "beta")
    assert _score(safe, plain) < 0.99


def test_kotlin_interpolated_string_is_not_a_plain_literal():
    interpolated = _function('    return "v=$a"')
    plain = _function('    return "v"', "beta")
    assert _score(interpolated, plain) < 1.0


CANDIDATES = """\
package demo

class Box {
    fun place(): Int {
        return 1
    }

    val size: Int
        get() {
            return 2
        }

    inline fun inl(): Int {
        return 3
    }

    init {
        println()
    }

    fun outer() {
        fun local() {}
        val o = object : Runnable {
            override fun run() {}
        }
    }

    companion object {
        fun make(): Box {
            return Box()
        }
    }
}

abstract class Shape {
    abstract fun area(): Int
}

enum class Color {
    RED {
        override fun hex(): Int {
            return 1
        }
    };

    abstract fun hex(): Int
}

fun String.shout() = uppercase()
"""


def test_kotlin_candidates_match_crapper():
    starts = [entry.start_line for entry in forms(CANDIDATES, "Box.kt")]
    assert starts == [4, 9, 21, 29, 41, 49]


def test_kotlin_detection(tmp_path):
    assert language_of("A.kt") == "kotlin"
    assert language_of("build.gradle.kts") is None
    write_source(tmp_path, "src/B.kt", "fun b() {}\n")
    write_source(tmp_path, ".claude/worktrees/x/A.kt", "fun a() {}\n")
    found = iter_source_files([tmp_path])
    assert [path.name for path in found] == ["B.kt"]


def test_kotlin_broken_source_does_not_raise():
    forms("fun broken( {\n", "B.kt")


def test_help_mentions_kotlin():
    from dryer.cli import HELP

    assert "Kotlin (.kt)" in HELP


def test_kotlin_infix_calls_keep_their_names():
    until = _function("    return (0 until 3).toList()")
    down = _function("    return (0 downTo 3).toList()", "beta")
    renamed = _function("    return (1 until 2).toList()", "beta")
    assert _score(until, down) < 0.99
    assert _score(until, renamed) == 1.0


def test_typescript_mapped_type_optional_is_not_an_operator():
    source = "function alpha<T>(x: { [K in keyof T]?: T[K] }) {\n  return x;\n}\n"
    entries, _warning = entries_in_source("typescript", source, "a.ts", "a.ts")
    assert not any("?:" in item for item in entries[0].fingerprints)
