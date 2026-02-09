# Specification: AI-Powered Image Adaptation ("Adapts")

## 1. Crisp Problem Description
Marketing and streaming platforms require a single creative asset (e.g., a movie poster or hero image) to be delivered in dozens of different formats, aspect ratios, and compositions. Examples include Netflix-style thumbnails (16:9), vertical posters (2:3), mobile app banners, and high-resolution print materials. 

Currently, this process is manually intensive, requiring designers to painstakingly crop, recompose, and reposition elements (like logos and text) for every single variation. This "manual resizing" is slow, expensive, and scales poorly as the number of distribution channels grows.

## 2. Key Challenges
### Technical Challenges
- **Saliency Preservation**: Automatically identifying the most important parts of an image (faces, products, action) to ensure they aren't cropped out during aspect ratio changes.
- **Composition Integrity**: Maintaining the "feel" and "story" of an image when moving from horizontal (16:9) to vertical (9:16).
- **Text & Brand Layering**: Intelligently placing titles, logos, and legal text so they don't obscure key visual elements or become unreadable.
- **Resolution & Quality**: Upscaling or intelligently filling gaps (outpainting) when the target size exceeds the source or requires a different composition.

### Business Challenges
- **Brand Consistency**: Ensuring that AI-generated adapts don't violate brand guidelines or artistic intent.
- **Speed vs. Quality**: Delivering results fast enough for real-time workflows without sacrificing professional aesthetic standards.

## 3. Technical Solution
### Summary
The system will use a **Pure Generative AI** pipeline powered by the **Gemini 3 Pro Image Preview** model. Unlike traditional cropping, the model will generate entirely new creative adaptations of the source image based on requested aspect ratios and resolutions.

### Mapping to Problems
| Problem/Challenge | Solution Component |
| :--- | :--- |
| **Saliency Preservation** | Gemini's generative capability automatically recomposes the scene to keep primary subjects central in the new aspect ratio. |
| **Composition Integrity** | Prompt-based instructions (e.g., "Rule of Thirds", "Cinematic Wide") guide Gemini to generate aesthetic compositions. |
| **Resolution & Quality** | Gemini generates the target resolution (HD, 4K) natively as part of the image-to-image task. |
| **Multi-Format Export** | Orchestrated parallel calls to Gemini for each requested format, saving returned image data directly to GCS. |

## 4. Success/Acceptance Criteria
- **Functional**: Users can upload one image, select aspect ratios, and get finished, high-quality images back.
- **Tuning**: Users can provide "Refinement Prompts" to adjust the generated output.
- **Performance**: A generated 4K adapt should be delivered in under 60 seconds.
- **UI**: Users can view the original and generated versions side-by-side.
- **Reliability**: System handles the binary image data returned by Gemini without corruption.

## 5. FAQs
**Q: Can it handle images with text already baked in?**
A: The initial version is optimized for "clean" art. Baked-in text may be treated as a salient object or cropped awkwardly.

**Q: Does it support outpainting for extreme aspect ratios?**
A: Version 1.0 focuses on intelligent cropping and recomposition. Generative outpainting (filling in the blanks) is a candidate for Version 2.0.

**Q: What file formats are supported?**
A: Source: JPG, PNG, WEBP, TIFF. Output: JPG, PNG, WEBP.

**Q: How does it know where to put the logo?**
A: Users can define "Safe Zones" or the system will suggest placements in areas with the lowest visual complexity (entropy).
