"""Unit tests for lottery parser."""

import json

from src.collector.parser import LotteryParser


class TestParseRoundList:
    """Test LotteryParser.parse_round_list."""

    SAMPLE_ROUND = {
        "psltEpsd": 1,
        "psltRflYmd": "20200507",
        "wnBndNo": "4",
        "wnRnkVl": "162132",
        "bnsRnkVl": "278239",
    }

    def test_parse_direct_list(self) -> None:
        """Parse a direct JSON array."""
        raw = json.dumps([self.SAMPLE_ROUND])
        rounds = LotteryParser.parse_round_list(raw)
        assert len(rounds) == 1
        assert rounds[0].round_number == 1
        assert rounds[0].group == 4
        assert rounds[0].numbers == [1, 6, 2, 1, 3, 2]

    def test_parse_nested_result(self) -> None:
        """Parse nested {result: [...]} format."""
        raw = json.dumps({"result": [self.SAMPLE_ROUND]})
        rounds = LotteryParser.parse_round_list(raw)
        assert len(rounds) == 1

    def test_parse_deep_nested(self) -> None:
        """Parse {data: {result: [...]}} format."""
        raw = json.dumps({"data": {"result": [self.SAMPLE_ROUND]}})
        rounds = LotteryParser.parse_round_list(raw)
        assert len(rounds) == 1

    def test_parse_empty_list(self) -> None:
        """Parse empty list returns empty."""
        raw = json.dumps([])
        rounds = LotteryParser.parse_round_list(raw)
        assert len(rounds) == 0

    def test_parse_invalid_json(self) -> None:
        """Invalid JSON returns empty list."""
        rounds = LotteryParser.parse_round_list("not valid json{{{")
        assert len(rounds) == 0

    def test_skips_invalid_records(self) -> None:
        """Invalid records are skipped, valid ones parsed."""
        data = [self.SAMPLE_ROUND, {"bad": "record"}, "not a dict"]
        raw = json.dumps(data)
        rounds = LotteryParser.parse_round_list(raw)
        assert len(rounds) == 1

    def test_sorts_by_round_number(self) -> None:
        """Results are sorted by round_number ascending."""
        r1 = {**self.SAMPLE_ROUND, "psltEpsd": 10}
        r2 = {**self.SAMPLE_ROUND, "psltEpsd": 3}
        r3 = {**self.SAMPLE_ROUND, "psltEpsd": 7}
        raw = json.dumps([r1, r2, r3])
        rounds = LotteryParser.parse_round_list(raw)
        assert [r.round_number for r in rounds] == [3, 7, 10]


class TestParseLatestRound:
    """Test LotteryParser.parse_latest_round."""

    def test_parse_valid_html(self) -> None:
        """Extract round number from HTML."""
        html = '<html><strong id="drwNo720">308</strong></html>'
        assert LotteryParser.parse_latest_round(html) == 308

    def test_missing_tag_returns_none(self) -> None:
        """Missing tag returns None."""
        html = "<html><body>nothing</body></html>"
        assert LotteryParser.parse_latest_round(html) is None
