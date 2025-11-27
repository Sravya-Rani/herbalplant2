# Wikipedia Uses Detection Improvements

## Problem
Many plants (like "Byrsonima spicata" / "Doncella") were showing fallback messages instead of actual uses from Wikipedia.

## Solutions Implemented

### 1. Enhanced Wikipedia Search Strategies

**Multiple Search Attempts:**
- ✅ Original query (scientific name or common name)
- ✅ Query without "sp." or "spp." abbreviations
- ✅ Genus name only (if species name fails)
- ✅ Common name variations
- ✅ With "herb", "plant", or "medicinal plant" suffix

### 2. Improved Wikipedia Fetching

**Two-Level Approach:**
1. **Summary API** - Fast, gets page summary
2. **Full Page API** - Falls back to full page if summary fails

**Better Extraction:**
- ✅ More keywords for medicinal uses detection
- ✅ Up to 8 sentences (increased from 6)
- ✅ Up to 1000 characters (increased from 800)
- ✅ Handles both summary and full page content

### 3. Web Search Fallback

**New Function:** `_search_web_for_uses()`
- Tries Wikipedia search API with medicinal queries
- Searches: "{name} medicinal uses", "{name} traditional medicine"
- Extracts relevant sentences from results

### 4. Enhanced Fallback Message

**More Informative:**
- Includes genus information when available
- Provides context about plant families
- Suggests consulting professionals
- Mentions common traditional uses

## Search Strategy Flow

```
1. Database Lookup
   ↓ (if not found)
2. Wikipedia - Scientific Name
   ↓ (if not found)
3. Wikipedia - Common Name
   ↓ (if not found)
4. Wikipedia - With "herb/plant" suffix
   ↓ (if not found)
5. Wikipedia - Genus Name
   ↓ (if not found)
6. Wikipedia Full Page - Scientific Name
   ↓ (if not found)
7. Wikipedia Full Page - Common Name
   ↓ (if not found)
8. Web Search - Medicinal Uses
   ↓ (if not found)
9. Informative Fallback Message
```

## Example: Byrsonima spicata

**Before:**
- Only tried "Byrsonima spicata" → Failed
- Showed generic fallback message

**After:**
- Tries "Byrsonima spicata" → May fail
- Tries "Byrsonima" (genus) → May succeed
- Tries "Doncella" (common name) → May succeed
- Tries "Doncella medicinal uses" → May succeed
- Falls back to informative message with genus info

## Testing

To verify improvements work:

1. Upload image of "Byrsonima spicata" or similar plant
2. Check if uses are now fetched from Wikipedia
3. Verify multiple search strategies are tried
4. Confirm informative message if all searches fail

## Files Modified

- `backend/services/herb_service.py`
  - Enhanced `_fetch_wikipedia_summary()` with multiple search terms
  - Added `_fetch_wikipedia_full_page()` for full page content
  - Added `_search_web_for_uses()` for web search fallback
  - Updated both PlantNet and Plant.id paths to use new strategies

---

**Status: ✅ Improved Wikipedia fetching with multiple fallback strategies**

The system should now successfully fetch uses for many more plants!

