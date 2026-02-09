# Story 1: Image Adaptation UI

## Summary
Create the frontend interface where users can upload an image, select their desired "Adapt Pack" (presets), and view the generated results in a gallery.

## Tasks
- [ ] Create `frontend/app/image-adapts/page.tsx`.
- [ ] Build `ImageUpload` component with preview.
- [ ] Build `AdaptPresetSelector` (Social Pack, Streaming Pack, Custom).
- [ ] Build `AdaptGallery` to display generated results from GCS.
- [ ] Integrate with `api-client.ts` for job creation and polling.

## Acceptance Criteria
- User can upload an image and see a thumbnail.
- User can select "16:9" and "9:16" and click "Generate".
- Gallery shows a loading state until the job is COMPLETED.
- Gallery displays all generated adapts with download buttons.

## Edge Cases
- User navigates away while job is processing.
- API returns error message (displayed as Toast).
- Large images cause slow frontend previews.

## Functional Tests
- E2E: User uploads image, selects presets, clicks generate, and sees 3 images appear.
- E2E: User attempts to generate without selecting a format; verify validation error.
- E2E: Verify that clicking "Download" on an adapt fetches the correct file from GCS.
