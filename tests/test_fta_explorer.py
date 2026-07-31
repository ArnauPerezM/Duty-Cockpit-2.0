from src.logic import extract_fta_programs_from_session_output


def test_extract_fta_programs_from_session_output():
    output = {
        "line": [
            {
                "rateProgram": [
                    {
                        "rateProgName": "FTA Test",
                        "rateProgResult": [
                            {
                                "ratePct": 0.0,
                                "rateDesc": "Zero duty",
                                "calcVal": 12.5,
                                "calcValCur": "EUR",
                            }
                        ],
                    }
                ]
            }
        ]
    }

    df = extract_fta_programs_from_session_output(output)

    assert not df.empty
    assert df.iloc[0]["Program"] == "FTA Test"
    assert df.iloc[0]["Rate %"] == 0.0
    assert df.iloc[0]["Description"] == "Zero duty"
