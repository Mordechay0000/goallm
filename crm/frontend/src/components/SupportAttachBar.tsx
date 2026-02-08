/**
 * Support message attachment bar: add file, screen recording, voice recording, traffic recording.
 * Handles errors for permission denied, no device, user cancel, upload failures.
 */
import React, { useRef, useState, useEffect } from 'react';
import { Button, Box, IconButton, Alert, LinearProgress } from '@mui/material';
import {
  AttachFile as AttachFileIcon,
  Mic as MicIcon,
  Videocam as VideocamIcon,
  Stop as StopIcon,
  Delete as DeleteIcon,
  Route as RouteIcon,
} from '@mui/icons-material';
import type { SupportAttachmentItem } from '../api/support';
import { getAvatarUrl } from '../api/auth';
import { trafficApi } from '../api/traffic';

function resolveUrl(url: string): string {
  return getAvatarUrl(url || '');
}

function getRecordingErrorMessage(err: unknown, kind: 'voice' | 'screen'): string {
  if (err instanceof DOMException) {
    switch (err.name) {
      case 'NotAllowedError':
      case 'PermissionDeniedError':
        return kind === 'voice'
          ? 'נדרשת הרשאת גישה למיקרופון. אנא אשר בדפדפן.'
          : 'נדרשת הרשאה לשיתוף המסך. אנא בחר חלון או מסך והאשר.';
      case 'NotFoundError':
        return kind === 'voice'
          ? 'לא נמצא מיקרופון. בדוק חיבור המכשיר.'
          : 'לא נמצא מקור להקלטה.';
      case 'NotReadableError':
        return 'המכשיר תפוס או לא זמין. נסה לסגור אפליקציות אחרות שמשתמשות בו.';
      case 'OverconstrainedError':
        return 'המכשיר לא תומך בדרישות ההקלטה.';
      case 'AbortError':
        return kind === 'screen' ? 'בוטל – לא נבחר מסך או חלון להקלטה.' : 'ההקלטה בוטלה.';
      default:
        return kind === 'voice' ? 'הקלטת הקול נכשלה.' : 'הסרטת המסך נכשלה.';
    }
  }
  return kind === 'voice' ? 'הקלטת הקול נכשלה.' : 'הסרטת המסך נכשלה.';
}

interface SupportAttachBarProps {
  onAttachmentsChange?: (list: SupportAttachmentItem[]) => void;
  attachments?: SupportAttachmentItem[];
  onUpload: (file: File, onProgress?: (percent: number) => void) => Promise<{ url: string; name: string }>;
  /** When set, every added file/recording/traffic is appended as markdown to the message content (no separate attachments). */
  onAppendContent?: (markdown: string) => void;
  disabled?: boolean;
  compact?: boolean;
  /** When set (e.g. -1), all buttons/icon-buttons get this tabIndex so Tab skips them. */
  buttonsTabIndex?: number;
}

export const SupportAttachBar: React.FC<SupportAttachBarProps> = ({
  onAttachmentsChange,
  attachments = [],
  onUpload,
  onAppendContent,
  disabled,
  compact,
  buttonsTabIndex,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const attachmentsRef = useRef(attachments);
  attachmentsRef.current = attachments;
  const onAppendContentRef = useRef(onAppendContent);
  onAppendContentRef.current = onAppendContent;

  const appendOrAttach = React.useCallback(
    (name: string, url: string, isTraffic = false) => {
      const fullUrl = url.startsWith('http') ? url : resolveUrl(url);
      const line = isTraffic ? `\n\n🔗 [${name}](${fullUrl})` : `\n\n📎 [${name}](${fullUrl})`;
      const append = onAppendContentRef.current;
      if (append) {
        append(line);
      } else if (onAttachmentsChange) {
        onAttachmentsChange([...attachmentsRef.current, { name, url }]);
      }
    },
    [onAttachmentsChange]
  );

  const [recording, setRecording] = useState<'voice' | 'screen' | null>(null);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [trafficRecording, setTrafficRecording] = useState(false);
  const [trafficLoading, setTrafficLoading] = useState(false);

  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 8000);
    return () => clearTimeout(t);
  }, [error]);

  useEffect(() => {
    const fetchTrafficStatus = () => {
      trafficApi.status().then((s) => setTrafficRecording(s.recording)).catch(() => setTrafficRecording(false));
    };
    fetchTrafficStatus();
    const id = setInterval(fetchTrafficStatus, 5000);
    return () => clearInterval(id);
  }, []);

  const handleTrafficRecording = async () => {
    setError(null);
    setTrafficLoading(true);
    try {
      if (trafficRecording) {
        const { share_token } = await trafficApi.stop();
        const viewUrl = trafficApi.getViewUrl(share_token);
        appendOrAttach('הקלטת תעבורה', viewUrl, true);
        setTrafficRecording(false);
      } else {
        await trafficApi.start();
        setTrafficRecording(true);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'שגיאה בהקלטת תעבורה. נסה שוב.';
      setError(msg);
    } finally {
      setTrafficLoading(false);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const input = e.target;
    const fileList = input.files;
    const filesArray = fileList ? Array.from(fileList) : [];
    if (!filesArray.length || disabled) return;
    input.value = '';
    setError(null);
    setUploading(true);
    setUploadProgress(null);
    try {
      for (let i = 0; i < filesArray.length; i++) {
        setUploadProgress(null);
        const file = filesArray[i];
        if (!file) continue;
        const info = await onUpload(file, (p) => setUploadProgress(p));
        appendOrAttach(info.name, info.url);
      }
    } catch (err) {
      const ax = err as { response?: { status?: number; data?: { detail?: string } }; message?: string };
      const detail = ax?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : err instanceof Error ? err.message : 'שגיאה בהעלאת הקובץ. נסה שוב.';
      setError(msg);
    } finally {
      setUploading(false);
      setUploadProgress(null);
    }
  };

  const removeAttachment = (index: number) => {
    onAttachmentsChange?.(attachments.filter((_, i) => i !== index));
  };

  const startVoiceRecording = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (ev) => ev.data.size && chunks.push(ev.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (chunks.length) {
          const blob = new Blob(chunks, { type: 'audio/webm' });
          const file = new File([blob], `voice-${Date.now()}.webm`, { type: 'audio/webm' });
          setUploading(true);
          setUploadProgress(null);
          setError(null);
          try {
            const info = await onUpload(file);
            appendOrAttach(info.name, info.url);
          } catch (err) {
            setError(err instanceof Error ? err.message : 'שגיאה בהעלאת ההקלטה.');
          } finally {
            setUploading(false);
            setUploadProgress(null);
          }
        }
      };
      recorder.start();
      setMediaRecorder(recorder);
      setRecording('voice');
    } catch (err) {
      setError(getRecordingErrorMessage(err, 'voice'));
    }
  };

  const startScreenRecording = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (ev) => ev.data.size && chunks.push(ev.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (chunks.length) {
          const blob = new Blob(chunks, { type: 'video/webm' });
          const file = new File([blob], `screen-${Date.now()}.webm`, { type: 'video/webm' });
          setUploading(true);
          setUploadProgress(null);
          setError(null);
          try {
            const info = await onUpload(file);
            appendOrAttach(info.name, info.url);
          } catch (err) {
            setError(err instanceof Error ? err.message : 'שגיאה בהעלאת ההסרטה.');
          } finally {
            setUploading(false);
            setUploadProgress(null);
          }
        }
      };
      recorder.start();
      setMediaRecorder(recorder);
      setRecording('screen');
    } catch (err) {
      setError(getRecordingErrorMessage(err, 'screen'));
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
      setMediaRecorder(null);
      setRecording(null);
    }
  };

  const btnSx = {
    textTransform: 'none',
    color: 'primary.main',
    fontSize: '0.8125rem',
    minWidth: 0,
    px: 1,
  };

  const showAttachmentsList = !onAppendContent && attachments.length > 0;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap', mb: showAttachmentsList ? 1 : 0 }}>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,.pdf,.webm,.mp4,.mp3,.wav,.txt,.md,.doc,.docx"
          style={{ display: 'none' }}
          onChange={handleFileSelect}
        />
        <Button
          type="button"
          size="small"
          startIcon={<AttachFileIcon sx={{ fontSize: 18 }} />}
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || uploading}
          sx={btnSx}
          tabIndex={buttonsTabIndex}
        >
          {compact ? 'קובץ' : 'הוסף קובץ או צילום מסך'}
        </Button>
        {recording === 'voice' ? (
          <Button size="small" startIcon={<StopIcon />} onClick={stopRecording} color="error" sx={{ ...btnSx, color: 'error.main' }} tabIndex={buttonsTabIndex}>
            עצור הקלטה
          </Button>
        ) : (
          <Button
            size="small"
            startIcon={<MicIcon sx={{ fontSize: 18 }} />}
            onClick={startVoiceRecording}
            disabled={disabled || uploading || recording !== null}
            sx={btnSx}
            tabIndex={buttonsTabIndex}
          >
            {compact ? 'אודיו' : 'הוסף הקלטת קול'}
          </Button>
        )}
        {recording === 'screen' ? (
          <Button size="small" startIcon={<StopIcon />} onClick={stopRecording} color="error" sx={{ ...btnSx, color: 'error.main' }} tabIndex={buttonsTabIndex}>
            עצור הקלטה
          </Button>
        ) : (
          <Button
            size="small"
            startIcon={<VideocamIcon sx={{ fontSize: 18 }} />}
            onClick={startScreenRecording}
            disabled={disabled || uploading || recording !== null}
            sx={btnSx}
            tabIndex={buttonsTabIndex}
          >
            {compact ? 'מסך' : 'הוסף הסרטת מסך'}
          </Button>
        )}
        {trafficRecording ? (
          <Button size="small" startIcon={<StopIcon />} onClick={handleTrafficRecording} color="error" sx={{ ...btnSx, color: 'error.main' }} tabIndex={buttonsTabIndex}>
            {compact ? 'סיום והצמדה' : 'סיום והצמדת קישור'}
          </Button>
        ) : (
          <Button
            size="small"
            startIcon={<RouteIcon sx={{ fontSize: 18 }} />}
            onClick={handleTrafficRecording}
            disabled={disabled || uploading || trafficLoading || recording !== null}
            sx={btnSx}
            tabIndex={buttonsTabIndex}
          >
            {compact ? 'תעבורה' : 'הקלטת תעבורה'}
          </Button>
        )}
      </Box>
      {uploading && (
        <LinearProgress
          variant={uploadProgress != null ? 'determinate' : 'indeterminate'}
          value={uploadProgress ?? 0}
          sx={{ mt: 1, mb: 0.5 }}
        />
      )}
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mt: 1 }}>
          {error}
        </Alert>
      )}
      {showAttachmentsList && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, alignItems: 'center' }}>
          {attachments.map((a, i) => (
            <Box
              key={`${a.url}-${i}`}
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 0.25,
                px: 1,
                py: 0.25,
                bgcolor: 'action.hover',
                borderRadius: 1,
                fontSize: '0.8125rem',
              }}
            >
              <a href={resolveUrl(a.url)} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit' }}>
                {a.name}
              </a>
              {!disabled && (
                <IconButton size="small" onClick={() => removeAttachment(i)} aria-label="הסר" sx={{ p: 0.25 }} tabIndex={buttonsTabIndex}>
                  <DeleteIcon sx={{ fontSize: 16 }} />
                </IconButton>
              )}
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
};

export default SupportAttachBar;
