from dataclasses import dataclass
@dataclass
class Shop:
    original_shop_name_address: str = ""
    original_district: str = ""
    row_index: int = 0
    pincode: str = ""
    latest_address: str = ""
    phone_number: str = ""
    business_status: str = ""
    verification_status: str = ""
    confidence_score: int = 0
    data_source: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    website: str = ""
    error_message: str = ""
    processed: bool = False
    
    # Extra fields
    business_name: str = ""
    business_category: str = ""
    open_closed_status: str = ""
    rating: str = ""
    review_count: str = ""
    google_maps_url: str = ""
    plus_code: str = ""
    place_id: str = ""
    
    @property
    def shop_name(self):
        return self.original_shop_name_address.split(",")[0] if "," in self.original_shop_name_address else self.original_shop_name_address
        
    @property
    def old_address(self):
        return self.original_shop_name_address

    def to_dict(self):
        return {
            "Shop Name + Old Address": self.original_shop_name_address,
            "District": self.original_district,
            "Pincode": self.pincode,
            "Latest Complete Address": self.latest_address,
            "Phone Number": self.phone_number,
            "Business Status": self.business_status,
            "Verification Status": self.verification_status,
            "Confidence Score": self.confidence_score,
            "Data Source": self.data_source,
            "Latitude": self.latitude,
            "Longitude": self.longitude,
            "Website": self.website,
            "Business Name": self.business_name,
            "Business Category": self.business_category,
            "Open/Closed Status": self.open_closed_status,
            "Ratings": self.rating,
            "Review Count": self.review_count,
            "Google Maps URL": self.google_maps_url,
            "Plus Code": self.plus_code,
            "Place ID": self.place_id,
            "Error Message": self.error_message
        }
