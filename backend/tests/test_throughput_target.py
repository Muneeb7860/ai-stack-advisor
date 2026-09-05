"""A stated rate is a scale signal. The engine could not read one.

Found by running a real OTP-verification design document through the engine. §8 says "At 300M/day,
the aggregate is material" — roughly 3,472 checks per second sustained. The engine returned
concurrencyTarget=None and highScale=False, so a whole dimension of the requirement was invisible
and the report sized the system as ordinary load.

Kept as its own signal rather than folded into detect_concurrency_target(). Concurrency is
simultaneous in-flight work; throughput is volume over time. They size different things, and
conflating them would compare "300M/day" against the million-concurrent-user band, declaring a
million-user system that does not exist.

Two false-positive families are guarded explicitly, because both appear in this corpus already:
prices ("$6/user/mo", "$1,500/yr" in the IAM vendor table) and retention periods ("retain audit
logs for 12 months"). `year` is absent from the unit table on purpose — annual figures in these
documents are money or contract terms, not traffic.
"""
import pytest

from app.rule_engine import (THROUGHPUT_HIGH_SCALE_RPS, detect_signals,
                             detect_throughput_target)


@pytest.mark.parametrize("text,expected_per_second", [
    ("At 300M/day, the aggregate is material.", 300_000_000 / 86400),
    ("We expect 5,000 requests per second at peak.", 5000),
    ("The system handles 2M messages a day.", 2_000_000 / 86400),
    ("Sustained 10k rps across the fleet.", 10_000),
    ("About 1.5M verifications per hour.", 1_500_000 / 3600),
    ("Roughly 90k events per minute.", 90_000 / 60),
])
def test_a_stated_rate_is_parsed_and_normalised_to_per_second(text, expected_per_second):
    got = detect_throughput_target(text)
    assert got is not None, f"no throughput parsed from {text!r}"
    assert got["perSecond"] == pytest.approx(expected_per_second, rel=1e-6)


@pytest.mark.parametrize("text", [
    # These two are rejected by the UNIT table ("mo"/"yr" are not units), not by the currency
    # guard — kept because they are real strings from this repo's own vendor tables.
    "Pricing is ~$6/user/mo for the starter tier.",
    "Okta bundled SSO+MFA with a ~$1,500/yr minimum.",
    # These are rejected ONLY by the currency guard: the unit is valid and the shape is identical
    # to a real rate. Added after a mutation run showed removing the guard broke nothing, because
    # every price case above happened to fail on the unit instead. The guard was untested.
    "Infrastructure budget is $5,000 per month.",
    "Egress runs about $200/day at current volume.",
    "That tier costs £900 per week.",
    "Retain audit logs for 12 months.",
    "The cap is 5 attempts per verification.",
    "Expect a response within 200 ms.",
])
def test_prices_retention_and_non_rate_phrases_are_not_throughput(text):
    """Over-reading is the worse failure: a fabricated scale figure would silently inflate the
    recommendation, and the ADR export states it back to the user as something they said."""
    assert detect_throughput_target(text) is None, f"{text!r} -> {detect_throughput_target(text)}"


def test_a_high_rate_trips_high_scale_without_any_keyword():
    """The reported document contains none of highScale's keywords — no "high traffic", no
    "millions of users". The figure alone has to carry it."""
    s = detect_signals("At 300M/day, the aggregate is material.")
    assert s["throughputTarget"]["perSecond"] > THROUGHPUT_HIGH_SCALE_RPS
    assert s["highScale"] is True


def test_a_low_rate_does_not_trip_high_scale():
    """The India DLT rule "a 20 msg/day cap" is a real rate and must stay far below the bar."""
    s = detect_signals("Warning, then a 20 msg/day cap for six months.")
    assert s["throughputTarget"]["perSecond"] < 1
    assert s["highScale"] is False


def test_the_largest_stated_rate_wins():
    s = detect_signals("Normally 2M messages a day, but 8k rps at peak.")
    assert s["throughputTarget"]["perSecond"] == pytest.approx(8000)
