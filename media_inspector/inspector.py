import os
from pymediainfo import MediaInfo
from .models import MediaMetadata, Track

class MediaInspectionError(Exception):
    pass

def inspect_media(file_path: str) -> dict:
    """
    Inspects a media file and returns its metadata.

    Args:
        file_path: The absolute path to the media file.

    Returns:
        A dictionary containing the media metadata.

    Raises:
        FileNotFoundError: If the file_path does not exist.
        MediaInspectionError: If the file is not a valid media file or cannot be inspected.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        media_info = MediaInfo.parse(file_path)
        if not media_info.tracks:
            raise MediaInspectionError("Not a valid media file or could not be inspected.")

        tracks = []
        for track in media_info.tracks:
            track_data = {
                "track_type": track.track_type,
                "format": track.format,
                "codec": track.codec,
                "bit_rate": track.bit_rate,
            }
            if track.track_type == 'Video':
                track_data.update({
                    "width": track.width,
                    "height": track.height,
                    "frame_rate": track.frame_rate,
                })
            elif track.track_type == 'Audio':
                track_data.update({
                    "sampling_rate": track.sampling_rate,
                    "channels": track.channel_s,
                })
            tracks.append(Track(**track_data))

        metadata = MediaMetadata(
            file_name=os.path.basename(file_path),
            file_size=os.path.getsize(file_path),
            duration=media_info.tracks[0].duration,
            tracks=tracks,
        )
        return metadata.dict()
    except Exception as e:
        raise MediaInspectionError(f"An error occurred during media inspection: {e}")
