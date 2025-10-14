# Super Over Alchemy - Demo Video Transcript

**Duration:** 2 minutes

---

## Introduction (0:00 - 0:15)

"Welcome to Super Over Alchemy - an AI-powered video analysis platform that combines Google Gemini with intelligent media processing. The platform features two main workflows: Media Processing and Scene Analysis. Let's dive in."

---

## Media Processing Workflow (0:15 - 0:45)

**[Screen: Media Processing page]**

"First, the Media Processing workflow. Upload any video or audio file directly to Google Cloud Storage."

**[Action: Click 'Upload Media', select file]**

"Configure your processing options - choose compression resolution from 360p to 4K, set CRF for quality control, and select encoding presets."

**[Screen: Processing configuration dialog]**

"For audio, extract in MP3, AAC, or WAV with custom bitrates. Click 'Start Processing' and the worker handles the rest."

**[Screen: Job dashboard showing completed job]**

"Track your jobs in real-time. Once complete, view compression ratios and download your processed files."

---

## Prompt Management (0:45 - 1:00)

**[Screen: Prompts page]**

"Before analyzing, let's look at Prompt Management. Create reusable analysis templates for different use cases - subtitling, object identification, key moments, or custom prompts."

**[Action: Click on a prompt]**

"Each prompt can support additional context files to enhance accuracy. This makes your analyses consistent and powerful."

---

## Scene Analysis Workflow (1:00 - 1:40)

**[Screen: Scene Analysis page]**

"Now for Scene Analysis. Start a new analysis and select media from your processed library."

**[Action: Click 'Start New Analysis', configure]**

"Choose your prompt - let's use 'Objects for Ads' to identify brand placements."

**[Screen: Context upload section]**

"Upload context files like brand guidelines or product specifications to improve detection accuracy."

**[Screen: Chunking options]**

"Configure chunking - process the entire file at once for better efficiency, or split into chunks for very long videos."

**[Action: Click 'Start Scene Analysis']**

"Submit the job and the scene worker processes it with Google Gemini 2.5 Pro."

**[Screen: Job results page with JSON]**

"Results come back as structured JSON - timestamped scene data, object detection, sentiment scores, and more. Download the results or view them directly in the interface."

---

## Closing (1:40 - 2:00)

**[Screen: Dashboard overview]**

"Super Over Alchemy brings together the power of Google Gemini AI, cloud-native architecture, and flexible processing options. Whether you're generating subtitles, identifying key moments, or analyzing brand placements - it's all here."

**[Screen: Project GitHub or logo]**

"Built with FastAPI, Next.js 15, and Google Cloud. Check out the GitHub repository to get started. Thanks for watching!"

---

## Key Talking Points to Emphasize

- **Dual workflow architecture** - separate media processing and scene analysis
- **Prompt-based flexibility** - reusable templates for different analysis types
- **Context file support** - upload additional files to enhance accuracy
- **Cloud-native design** - built on GCS, Firestore, and Gemini AI
- **Structured outputs** - JSON results with timestamps and metadata
- **Worker-based processing** - scalable background job execution

## Demo Tips

1. **Pre-record the upload** - File uploads can take time, have a completed upload ready
2. **Use a short video** - 30-second clip processes faster for live demo
3. **Have results ready** - Show a pre-completed analysis for the results section
4. **Keep moving** - 2 minutes goes fast, stay on pace
5. **Show the UI** - Highlight the clean interface and navigation
