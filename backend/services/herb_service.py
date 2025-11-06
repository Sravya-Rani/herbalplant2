import base64
import httpx

PLANT_ID_API_KEY = "nGCgk6QzBRjqUhvLLVJ0USSjdQNCvW74Qe4e3fhhEexFugDufg"
PLANT_ID_API_URL = "https://plant.id/api/v3/identification"

def identify_herb(image_path: str):
    """
    Identifies herb by sending image to Plant.id API.
    """
    with open(image_path, "rb") as img_file:
        image_base64 = base64.b64encode(img_file.read()).decode("utf-8")

    # Leave out 'modifiers' for basic identification.
    payload = {
        "api_key": PLANT_ID_API_KEY,
        "images": [image_base64],
        "plant_language": "en",
        "plant_details": ["common_names", "url", "name_authority", "wiki_description", "taxonomy"]
       
    }

    try:
        response = httpx.post(PLANT_ID_API_URL, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            print("Plant.id API response:", data)

            if "suggestions" in data and data["suggestions"]:
                suggestion = data["suggestions"][0]
                common_name = suggestion.get("plant_details", {}).get("common_names", ["Unknown"])[0]
                scientific_name = suggestion.get("plant_name", "Unknown")
                uses = suggestion.get("plant_details", {}).get("wiki_description", {}).get("value", "No info available.")
                return {
                    "common_name": common_name,
                    "scientific_name": scientific_name,
                    "uses": uses
                }
            else:
                print("No suggestions found in API response.")
                return {
                    "common_name": "Unknown herb",
                    "scientific_name": "N/A",
                    "uses": "No information available. Try uploading a clearer image."
                }
        else:
            print(f"API call failed with status: {response.status_code}")
            print("API error response:", response.text)
            return {
                "common_name": "Unknown herb",
                "scientific_name": "N/A",
                "uses": f"API call failed with status code {response.status_code}. API response: {response.text}"
            }
    except Exception as e:
        print("Plant.id API error:", e)
        return {
            "common_name": "Unknown herb",
            "scientific_name": "N/A",
            "uses": "An error occurred during plant identification. Please try again later."
        }
