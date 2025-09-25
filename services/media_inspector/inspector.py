import os
from pymediainfo import MediaInfo
from .models import MediaMetadata, Track
from common.storage import StorageManager

class MediaInspectionError(Exception):
    pass

def inspect_media(file_path: str) -> dict:
    """
    Inspects a media file (local or GCS) and returns its metadata.
    """
    storage = StorageManager()
    local_path = storage.get_local_path(file_path)

    try:
        media_info = MediaInfo.parse(local_path)
        if not media_info.tracks:
            raise MediaInspectionError("Not a valid media file or could not be inspected.")

        tracks = []
        for track in media_info.tracks:
            track_data = track.to_data()
            tracks.append(Track(**track_data))

        metadata = MediaMetadata(
            file_name=os.path.basename(file_path),
            file_size=os.path.getsize(local_path),
            duration=media_info.tracks[0].duration if media_info.tracks else 0,
            tracks=tracks,
        )
        return metadata.dict()
    except Exception as e:
        raise MediaInspectionError(f"An error occurred during media inspection: {e}")
    finally:
        storage.cleanup_temp_files()