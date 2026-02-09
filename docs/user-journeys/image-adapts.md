# User Journeys: Image Adaptation ("Adapts")

## Personas

### 1. Sarah, Senior Social Media Manager
- **Context**: Works at a major movie studio.
- **Pain Point**: Spends 4+ hours per campaign manually cropping hero art for Instagram (4:5), TikTok (9:16), Facebook (1.91:1), and Twitter (16:9).
- **Goal**: Rapidly generate a consistent "Social Pack" from a single high-res poster.

### 2. Marcus, Content Ops Lead at a Streaming Service
- **Context**: Manages thousands of titles on a platform like Netflix or Disney+.
- **Pain Point**: Needs to ensure thumbnails are compelling on TVs, mobile phones, and web browsers without losing the lead actor's face.
- **Goal**: Automate the creation of 16:9, 4:3, and 1:1 thumbnails that preserve key character expressions.

### 3. David, Print Production Designer
- **Context**: Prepares marketing materials for physical theaters.
- **Pain Point**: Needs to adapt wide landscape art into tall vertical banners for theater lobbies.
- **Goal**: Get a "smart crop" that doesn't just center-cut, but intelligently selects the most action-packed area.

---

## User Journeys

### Journey 1: The "Social Media Blast" (Persona: Sarah)
1. **Upload**: Sarah uploads a high-resolution 2:3 theatrical poster.
2. **Selection**: She selects the "Social Media Pack" preset from the dashboard.
3. **Processing**: The system uses **Gemini 3 Pro Image Preview** to identify the lead actress and the movie logo.
4. **Preview**: Sarah is presented with a gallery showing the 9:16, 4:5, and 16:9 adapts.
5. **Adjustment**: She notices the 9:16 crop is slightly off-center for the actress's face and uses the "Manual Tweak" tool to slide the crop 10% to the right.
6. **Download**: She downloads the entire pack as a ZIP file.

### Journey 2: Automated Thumbnailing (Persona: Marcus)
1. **Bulk Upload**: Marcus uploads 50 different "Hero Frames" from a new series.
2. **Configuration**: He selects the "Streaming Thumbnail Pack" (16:9, 4:3, 1:1).
3. **Intelligence**: **Gemini 3 Pro Image Preview** analyzes each frame, ensuring that if two characters are on screen, both are kept in the crop whenever possible.
4. **Quality Check**: Marcus scrolls through the generated adapts. The system highlights 2 images with "Low Confidence" where the crop might be suboptimal.
5. **Correction**: Marcus quickly fixes the 2 flagged images.
6. **Export**: He clicks "Export to CDN" to push the assets directly to the streaming platform's storage.

### Journey 3: The "Banner Adaptation" (Persona: David)
1. **Upload**: David uploads a 21:9 ultra-wide panoramic shot of a battle scene.
2. **Requirement**: He needs a 2:3 vertical banner for a lobby standee.
3. **Analysis**: The system identifies that the main "Action POI" is on the far left of the panoramic shot.
4. **Result**: Instead of a generic center crop (which would show empty sky), the system generates a 2:3 vertical crop focused on the battle action.
5. **Approval**: David approves the crop and downloads the high-res TIFF version for printing.
