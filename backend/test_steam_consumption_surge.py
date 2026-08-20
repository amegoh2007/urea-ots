import pytest
from main import stripper_322e001, STRIP_DUTY_RAW_DES_KW, CO2_DES_KGH, STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA, STRIP_FEED207_KMOLH, STRIP_FEED207_T_C

def test_steam_consumption_increases_on_surge():
    feed_base = STRIP_FEED207_KMOLH.copy()
    base = stripper_322e001(CO2_DES_KGH/1000.0, STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA, feed_base, None, None, STRIP_FEED207_T_C)
    
    # 20% surge in feed
    feed_surge = {k: v * 1.2 for k, v in feed_base.items()}
    surge = stripper_322e001(CO2_DES_KGH/1000.0, STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA, feed_surge, None, None, STRIP_FEED207_T_C)
    
    base_ratio = base['duty_raw_kw'] / STRIP_DUTY_RAW_DES_KW
    surge_ratio = surge['duty_raw_kw'] / STRIP_DUTY_RAW_DES_KW
    
    # The absolute duty (and thus steam consumption) must INCREASE during a surge
    assert surge_ratio > base_ratio, f"Expected duty to increase on surge, but got {surge_ratio} <= {base_ratio}"
