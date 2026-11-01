from money import format_money, round_money


def test_round_half_up():
    assert round_money(2.675) == 2.68


def test_format():
    assert format_money(1234.5) == "Rs 1,234.50"
