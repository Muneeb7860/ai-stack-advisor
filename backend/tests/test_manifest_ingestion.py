"""Dependency-manifest ingestion: start from what you actually run.

A brownfield user can now hand over a package.json, requirements.txt, go.mod, Gemfile, pom.xml or
docker-compose.yml instead of re-describing their stack in prose. It reuses the diagram upload's
confirm-the-chips flow and its funnel — parse, confirm, synthesize a sentence, then the same
setAnalysis(text, detectSignals(text)) every other entry mode goes through. No rule-engine change,
so no dual-engine parity surface.

The failure mode this feature invites is a convincing one: parse a manifest, render chips full of
real dependency names, and change nothing, because the names mean nothing to the engines. A chip
reading "psycopg2-binary" looks like understanding and produces exactly the same recommendations
as an empty input. So the load-bearing test here is not "does it parse" — it is
test_every_mapped_term_is_recognised_by_the_engine, which derives the permitted vocabulary from
KNOWN_TERMS and detectSignals' own phrase lists rather than restating it, plus
test_a_manifest_actually_changes_the_recommendation, which asserts the output moves.

Unrecognised packages are dropped rather than passed through as raw text. An unrecognised chip
claims to the user that something was understood when it was not.

One wording decision is load-bearing and easy to get backwards. The natural phrasing for the
synthesized sentence — "we already have an existing application" — is the authoritative trigger
for detectSignals' brownfieldAiOnly, which SUPPRESSES the infrastructure sections. That is correct
for the wizard's brownfield "only add AI" path and exactly wrong here: someone who just handed
over their package.json is asking about their infrastructure. Asserted below.
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)


def _text() -> str:
    return INDEX.read_text(encoding="utf-8")


def _main_script() -> str:
    return _text().split("<script>")[2].split("</script>")[0]


_STUBS = r"""
const dummyEl={style:{},classList:{add(){},remove(){},toggle(){},contains:()=>false},addEventListener(){},
  setAttribute(){},getAttribute:()=>null,appendChild(){},removeChild(){},click(){},focus(){},
  querySelector:()=>dummyEl,querySelectorAll:()=>[],innerHTML:'',textContent:'',value:''};
global.window={innerWidth:1280,location:{search:''},addEventListener(){},matchMedia:()=>({matches:false,addEventListener(){}})};
global.document={documentElement:dummyEl,body:dummyEl,querySelector:()=>dummyEl,querySelectorAll:()=>[],
  getElementById:()=>dummyEl,createElement:()=>dummyEl,addEventListener(){}};
global.navigator={clipboard:{}};global.localStorage={getItem:()=>null,setItem(){},removeItem(){}};
global.fetch=()=>Promise.resolve({ok:false});global.URL={createObjectURL:()=>'',revokeObjectURL(){}};
global.requestAnimationFrame=(fn)=>fn();
"""


def _js(body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + body)


PACKAGE_JSON = json.dumps({
    "dependencies": {"express": "^4", "pg": "^8", "ioredis": "^5", "react": "^18", "lodash": "^4"},
    "devDependencies": {"jest": "^29"},
})
REQUIREMENTS = "Django==4.2\npsycopg2-binary==2.9.9\nredis>=5.0\n# a comment\nrequests==2.31\n"
GO_MOD = "module x\n\ngo 1.22\n\nrequire (\n\tgithub.com/lib/pq v1.10.9\n\tgithub.com/IBM/sarama v1.43.0\n)\n"
COMPOSE = "services:\n  db:\n    image: postgres:16-alpine\n  broker:\n    image: confluentinc/cp-kafka:7.5.0\n"


def _parse(content: str, filename: str):
    return _js(f"console.log(JSON.stringify(parseDiagramInput({json.dumps(content)}, "
               f"{json.dumps(filename)})));")


# ------------------------------------------------------- the assertion that makes this real

@requires_node
def test_every_mapped_term_is_recognised_by_the_engine():
    """The whole feature rests on this. A mapping that emits a term neither vocabulary knows
    produces a convincing chip and identical recommendations — it looks like it works and does
    nothing.

    The permitted vocabulary is DERIVED here, from KNOWN_TERMS and from detectSignals' own
    has()/hasRaw() phrase lists, rather than restated as a list in this file. A restated copy
    would drift, and would then be asserting agreement with itself.
    """
    script = _text()
    known = set()
    m = re.search(r"const KNOWN_TERMS\s*=\s*\{(.*?)\n\};", script, re.S)
    assert m, "KNOWN_TERMS not found"
    for _key, arr in re.findall(r"(\w+):\[([^\]]*)\]", m.group(1)):
        known.update(s.strip().lower() for s in re.findall(r"'([^']*)'", arr))

    start = script.index("function detectSignals(text){")
    body = re.sub(r"//[^\n]*", "",
                  script[start:script.index("\n}", script.index("return {", start))])
    for arr in re.findall(r"has(?:Raw)?\(\[([^\]]*)\]\)", body):
        known.update(s.strip().lower() for s in re.findall(r"'([^']*)'", arr))

    mapped = _js("console.log(JSON.stringify(Array.from(new Set("
                 "Object.values(MANIFEST_TECH_MAP).concat(MANIFEST_IMAGE_HINTS.map(h=>h[1]))))));")

    unrecognised = []
    for term in mapped:
        t = term.lower()
        if not any(t in vocab or vocab in t for vocab in known):
            unrecognised.append(term)
    assert not unrecognised, (
        f"these manifest terms match nothing either engine looks for, so detecting them changes "
        f"no recommendation: {unrecognised}"
    )


@requires_node
def test_a_manifest_actually_changes_the_recommendation():
    """The behavioural half. Parsing correctly is worth nothing if the synthesized sentence
    leaves the output identical to an empty one."""
    out = _js("""
      const terms = parseDiagramInput(%s, 'package.json').entities.map(e => e.text);
      const withM = 'Current stack detected from a dependency manifest: ' + terms.join(', ')
        + '. Assess this stack and recommend what to keep, what to change, and what is missing.';
      const without = 'Assess this stack and recommend what to keep, what to change, and what is missing.';
      const a = computeRecommendations(detectSignals(withM));
      const b = computeRecommendations(detectSignals(without));
      const changed = {};
      ['db','cache','msg','lang','compute'].forEach(k => {
        if (a[k] && b[k] && a[k].v !== b[k].v) changed[k] = [b[k].v, a[k].v];
      });
      console.log(JSON.stringify(changed));
    """ % json.dumps(PACKAGE_JSON))
    assert out, "a parsed manifest changed nothing in the recommendation"
    assert "cache" in out, f"a manifest naming Redis should affect the cache pick; changed: {out}"


# --------------------------------------------------------------------------- the parsers

@requires_node
@pytest.mark.parametrize("filename,content,expected", [
    ("package.json", PACKAGE_JSON, {"Node.js", "PostgreSQL", "Redis", "React"}),
    ("requirements.txt", REQUIREMENTS, {"Django", "PostgreSQL", "Redis"}),
    ("go.mod", GO_MOD, {"PostgreSQL", "Kafka"}),
    ("docker-compose.yml", COMPOSE, {"PostgreSQL", "Kafka"}),
    ("Gemfile", "gem 'rails'\ngem 'pg'\ngem 'redis'\n", {"Rails", "PostgreSQL", "Redis"}),
    ("pom.xml", "<artifactId>spring-boot-starter-web</artifactId><artifactId>postgresql</artifactId>",
     {"Spring Boot", "PostgreSQL"}),
])
def test_each_manifest_format_yields_its_technologies(filename, content, expected):
    out = _parse(content, filename)
    assert out["type"] == "manifest"
    assert set(e["text"] for e in out["entities"]) == expected


@requires_node
def test_unrecognised_packages_are_dropped_not_passed_through():
    """lodash, jest and requests appear in the fixtures above and must not become chips. A chip
    the engine cannot act on tells the user something was understood when it was not."""
    for content, name in ((PACKAGE_JSON, "package.json"), (REQUIREMENTS, "requirements.txt")):
        terms = {e["text"] for e in _parse(content, name)["entities"]}
        assert not (terms & {"lodash", "jest", "requests"})


@requires_node
def test_go_module_paths_reduce_to_their_recognisable_tail():
    """github.com/lib/pq has to reach PostgreSQL. Found by running a real go.mod through this:
    the tail is "pq", which matched nothing, so a Postgres-backed Go service reported only its
    cache and silently understated the stack."""
    terms = {e["text"] for e in _parse(GO_MOD, "go.mod")["entities"]}
    assert "PostgreSQL" in terms


@requires_node
def test_docker_images_match_despite_registry_and_tag():
    """Images carry registries and tags — confluentinc/cp-kafka:7.5.0 — so they are matched by
    fragment, unlike package names which are matched exactly."""
    terms = {e["text"] for e in _parse(COMPOSE, "docker-compose.yml")["entities"]}
    assert {"PostgreSQL", "Kafka"} <= terms


@requires_node
def test_a_duplicate_technology_appears_once():
    """psycopg2 and asyncpg in one file are still one PostgreSQL."""
    out = _parse("psycopg2==2.9\nasyncpg==0.29\npsycopg2-binary==2.9\n", "requirements.txt")
    assert [e["text"] for e in out["entities"]] == ["PostgreSQL"]


@requires_node
@pytest.mark.parametrize("content,name", [
    ("{ not json at all ", "package.json"),
    ("", "package.json"),
    ("{}", "package.json"),
    ("\n\n# only comments\n", "requirements.txt"),
])
def test_unparseable_or_empty_manifests_fall_through_quietly(content, name):
    """A file that merely shares a manifest's name should reach the diagram parsers rather than
    raise — the fallback is the correct outcome, not an error dialog."""
    out = _parse(content, name)
    assert out["type"] != "manifest" or not out["entities"]


@requires_node
def test_a_diagram_is_still_parsed_as_a_diagram():
    """The manifest check runs first, so this guards against it capturing everything."""
    out = _parse("graph TD\n  A[API Gateway] --> B[PostgreSQL]\n", "arch.mmd")
    assert out["type"] == "mermaid"


# ------------------------------------------------------------------------ the framing

def test_the_synthesized_text_does_not_trigger_the_ai_only_suppression():
    """The trap. "we already have an existing application" is the authoritative trigger for
    brownfieldAiOnly, which SUPPRESSES the infrastructure sections. Right for the wizard's
    "only add AI" path; exactly wrong for someone who just handed over their package.json and is
    asking about infrastructure."""
    m = re.search(r"const synthesizedText = uploadedSourceKind === 'manifest'\s*\?(.*?);",
                  _text(), re.S)
    assert m, "the manifest branch of the synthesized text was not found"
    manifest_copy = m.group(1).lower()
    for trigger in ("already have an existing app", "already have an existing application",
                    "existing application in production", "only want to add ai"):
        assert trigger not in manifest_copy, (
            f"the manifest wording contains {trigger!r}, which fires brownfieldAiOnly and hides "
            f"the infrastructure sections the user came for"
        )


def _manifest_sentence_expression() -> str:
    """The manifest branch of analyzeDiagramEntities' synthesized text, lifted from the source.

    Extracted rather than retyped. The first version of the test below embedded its own copy of
    the sentence, so changing the real wording to the brownfieldAiOnly trigger phrase left it
    green — it was asserting against itself while the app suppressed the infrastructure sections.
    Mutation testing caught that; this now exercises the string the app actually builds.
    """
    m = re.search(r"const synthesizedText = uploadedSourceKind === 'manifest'\s*\?(.*?)\n\s*:",
                  _text(), re.S)
    assert m, "the manifest branch of the synthesized text was not found"
    return m.group(1).strip()


@requires_node
def test_brownfield_ai_only_stays_off_for_a_real_manifest():
    """The behavioural version of the test above: runs the app's own sentence through the real
    signal detector, rather than asserting on how the source is worded."""
    out = _js("""
      const activeEntities = parseDiagramInput(%s, 'package.json').entities.map(e => e.text);
      const sentence = %s;
      console.log(JSON.stringify({
        aiOnly: detectSignals(sentence).brownfieldAiOnly === true,
        sentence: sentence
      }));
    """ % (json.dumps(PACKAGE_JSON), _manifest_sentence_expression()))
    assert out["aiOnly"] is False, (
        f"the shipped wording fires brownfieldAiOnly and hides the infrastructure sections: "
        f"{out['sentence']!r}"
    )


@requires_node
def test_the_shipped_wording_still_carries_the_detected_technologies():
    """The other half: wording that avoids the trigger is worthless if it also drops the terms.
    Guards against 'fixing' the suppression by removing the technology names."""
    out = _js("""
      const activeEntities = parseDiagramInput(%s, 'package.json').entities.map(e => e.text);
      const sentence = %s;
      const s = detectSignals(sentence);
      console.log(JSON.stringify({
        postgres: s.postgresMentioned === true,
        redis: s.redisMentioned === true,
        node: s.nodeMentioned === true
      }));
    """ % (json.dumps(PACKAGE_JSON), _manifest_sentence_expression()))
    assert all(out.values()), f"the shipped sentence loses detected technologies: {out}"


def test_manifest_and_diagram_uploads_are_labelled_differently():
    """A package.json yields technologies, not diagram components; reusing the diagram badge would
    misdescribe what the user is being asked to confirm."""
    m = re.search(r"function displayDiagramPreview\(.*?\n\}", _text(), re.S)
    assert m
    body = m.group(0)
    assert "uploadedSourceKind" in body
    assert "technolog" in body.lower() and "components detected" in body


def test_the_upload_screen_says_manifests_are_accepted():
    """It previously described diagrams only, so the capability would have been invisible."""
    text = _text()
    m = re.search(r'<input type="file" id="diagramFileInput"[^>]*accept="([^"]*)"', text)
    assert m, "the file input was not found"
    assert ".json" in m.group(1), "package.json cannot be chosen in the file picker"
    screen = text[text.index('id="screenUpload"'):]
    screen = screen[:screen.index("</div>\n</div>")] if "</div>\n</div>" in screen else screen[:6000]
    assert "package.json" in screen
