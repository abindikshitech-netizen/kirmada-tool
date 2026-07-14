from rapidfuzz import fuzz
from models.shop import Shop
from constants import STATUS_MANUAL_REVIEW

class VerificationEngine:
    @staticmethod
    def verify(shop: Shop):
        score = 0
        if shop.shop_name and shop.latest_address:
            match_score = fuzz.token_set_ratio(shop.original_shop_name_address.lower(), shop.latest_address.lower())
            score = int(match_score)
            
        shop.confidence_score = score
        if score >= 80:
            shop.verification_status = "Verified"
        elif score >= 60:
            shop.verification_status = "Likely Match"
        else:
            shop.verification_status = STATUS_MANUAL_REVIEW
