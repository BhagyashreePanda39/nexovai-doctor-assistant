import { DeviceError, RTVIEvent } from "@pipecat-ai/client-js";
import {
  usePipecatClient,
  usePipecatClientMicControl,
  useRTVIClientEvent,
} from "@pipecat-ai/client-react";
import { useCallback, useEffect, useRef, useState } from "react";

import Icon from "./Icon.jsx";
import { API_BASE_URL } from "../services/api.js";

function getDeviceErrorMessage(error) {
  if (error instanceof DeviceError && error.devices.includes("mic")) {
    if (error.type === "permissions") {
      return "Microphone permission was denied. Allow microphone access for this site, then try again.";
    }
    if (error.type === "not-found") {
      return "No microphone was found. Connect a microphone and try again.";
    }
    if (error.type === "in-use") {
      return "The microphone is being used by another application. Close that app and try again.";
    }
    return error.message || "The microphone could not be started.";
  }

  if (
    error instanceof DOMException &&
    (error.name === "NotAllowedError" || error.name === "SecurityError")
  ) {
    return "Microphone permission was denied. Allow microphone access for this site, then try again.";
  }

  return null;
}

async function getConnectionErrorMessage(error) {
  const deviceMessage = getDeviceErrorMessage(error);
  if (deviceMessage) {
    return deviceMessage;
  }

  const response = error instanceof Error ? error.cause : null;
  if (response instanceof Response) {
    const body = await response.clone().json().catch(() => null);
    if (typeof body?.detail === "string") {
      return body.detail;
    }
    return `Voice service rejected the connection (HTTP ${response.status}).`;
  }

  if (error instanceof Error && error.cause instanceof DOMException) {
    return getDeviceErrorMessage(error.cause) || error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Could not connect to the voice assistant.";
}

function getServerErrorMessage(message) {
  const data = message?.data;
  if (data && typeof data === "object") {
    if ("error" in data && typeof data.error === "string") {
      return data.error;
    }
    if ("message" in data && typeof data.message === "string") {
      return data.message;
    }
  }
  return "The voice service reported an error. End the call and try again.";
}

function formatClock(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function formatDuration(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function VoiceAssistantDialog({ onClose, onAppointmentChange }) {
  const client = usePipecatClient();
  const { enableMic, isMicEnabled } = usePipecatClientMicControl();
  const [status, setStatus] = useState("Disconnected");
  const [isConnecting, setIsConnecting] = useState(false);
  const [isEnding, setIsEnding] = useState(false);
  const [error, setError] = useState("");
  const [messages, setMessages] = useState([]);
  const [connectedAt, setConnectedAt] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [audioLevels, setAudioLevels] = useState({ local: 0, remote: 0 });
  const [isVisible, setIsVisible] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const partialUserMessageId = useRef(null);
  const partialAssistantMessageId = useRef(null);
  const transcriptRef = useRef(null);
  const endingCallRef = useRef(false);
  const closeTimerRef = useRef(null);

  useEffect(() => {
    const frameId = window.requestAnimationFrame(() => setIsVisible(true));
    return () => {
      window.cancelAnimationFrame(frameId);
      if (closeTimerRef.current !== null) {
        window.clearTimeout(closeTimerRef.current);
      }
    };
  }, []);

  function animateClose() {
    setIsClosing(true);
    setIsVisible(false);
    closeTimerRef.current = window.setTimeout(onClose, 180);
  }

  const markConnected = useCallback(() => {
    endingCallRef.current = false;
    setStatus("Connected");
    setError("");
    setConnectedAt((current) => current || Date.now());
  }, []);

  const markDisconnected = useCallback(() => {
    setStatus(endingCallRef.current ? "Ended" : "Disconnected");
    setConnectedAt(null);
    setIsConnecting(false);
    setAudioLevels({ local: 0, remote: 0 });
  }, []);

  const handleUserInput = useCallback((data) => {
    const text = data.text?.trim();
    if (!text) {
      return;
    }

    const timestamp = data.timestamp || new Date().toISOString();
    setMessages((current) => {
      if (!data.final) {
        const existingId = partialUserMessageId.current;
        if (existingId) {
          return current.map((message) =>
            message.id === existingId
              ? { ...message, text, timestamp, final: false }
              : message,
          );
        }

        const id = crypto.randomUUID();
        partialUserMessageId.current = id;
        return [
          ...current,
          { id, speaker: "user", text, timestamp, final: false },
        ];
      }

      const id = partialUserMessageId.current || crypto.randomUUID();
      partialUserMessageId.current = null;
      const existing = current.some((message) => message.id === id);
      if (existing) {
        return current.map((message) =>
          message.id === id ? { ...message, text, final: true } : message,
        );
      }
      return [
        ...current,
        { id, speaker: "user", text, timestamp, final: true },
      ];
    });
  }, []);

  const handleBotOutput = useCallback(
    (data) => {
      if (data.will_be_spoken === false) {
        return;
      }

      const text =
        data.spoken_status === "in-progress"
          ? data.spoken_progress?.accumulated_text || data.text
          : data.text;
      if (!text?.trim()) {
        return;
      }

      const isFinal =
        data.spoken_status == null || data.spoken_status === "completed";
      const id =
        data.segment_id == null
          ? partialAssistantMessageId.current ||
            `assistant-${crypto.randomUUID()}`
          : `assistant-${data.segment_id}`;
      if (data.segment_id == null) {
        partialAssistantMessageId.current = isFinal ? null : id;
      }

      setMessages((current) => {
        const existing = current.some((message) => message.id === id);
        if (!existing) {
          return [
            ...current,
            {
              id,
              speaker: "assistant",
              text,
              timestamp: new Date().toISOString(),
              final: isFinal,
            },
          ];
        }
        return current.map((message) =>
          message.id === id ? { ...message, text, final: isFinal } : message,
        );
      });

      if (
        isFinal &&
        /\b(booked|cancelled|canceled)\b/i.test(text)
      ) {
        void onAppointmentChange();
      }
    },
    [onAppointmentChange],
  );

  const handleTransportState = useCallback((transportState) => {
    if (transportState === "connected" || transportState === "ready") {
      markConnected();
    } else if (transportState === "disconnected") {
      markDisconnected();
    } else if (transportState === "error") {
      setStatus("Error");
      setConnectedAt(null);
    } else {
      setStatus("Connecting");
    }
  }, [markConnected, markDisconnected]);

  const handleDeviceError = useCallback((deviceError) => {
    setStatus("Error");
    setError(
      getDeviceErrorMessage(deviceError) ||
        "A microphone or audio device error prevented the call from starting.",
    );
    setConnectedAt(null);
  }, []);

  const handleServerError = useCallback((serverError) => {
    setStatus("Error");
    setError(getServerErrorMessage(serverError));
  }, []);

  const handleLocalAudioLevel = useCallback((level) => {
    setAudioLevels((current) => ({
      ...current,
      local: Math.max(0, Math.min(1, level)),
    }));
  }, []);

  const handleRemoteAudioLevel = useCallback((level) => {
    setAudioLevels((current) => ({
      ...current,
      remote: Math.max(0, Math.min(1, level)),
    }));
  }, []);

  useRTVIClientEvent(RTVIEvent.UserInput, handleUserInput);
  useRTVIClientEvent(RTVIEvent.BotOutput, handleBotOutput);
  useRTVIClientEvent(RTVIEvent.Connected, markConnected);
  useRTVIClientEvent(RTVIEvent.Disconnected, markDisconnected);
  useRTVIClientEvent(RTVIEvent.TransportStateChanged, handleTransportState);
  useRTVIClientEvent(RTVIEvent.DeviceError, handleDeviceError);
  useRTVIClientEvent(RTVIEvent.Error, handleServerError);
  useRTVIClientEvent(RTVIEvent.LocalAudioLevel, handleLocalAudioLevel);
  useRTVIClientEvent(RTVIEvent.RemoteAudioLevel, handleRemoteAudioLevel);

  useEffect(() => {
    if (!connectedAt) {
      return undefined;
    }

    const updateTimer = () => {
      setElapsedSeconds(Math.floor((Date.now() - connectedAt) / 1000));
    };
    updateTimer();
    const intervalId = window.setInterval(updateTimer, 1000);
    return () => window.clearInterval(intervalId);
  }, [connectedAt]);

  useEffect(() => {
    const transcript = transcriptRef.current;
    if (transcript) {
      transcript.scrollTop = transcript.scrollHeight;
    }
  }, [messages]);

  async function connect() {
    if (!client || isConnecting || isEnding) {
      return;
    }

    setIsConnecting(true);
    setError("");
    setMessages([]);
    setElapsedSeconds(0);
    setAudioLevels({ local: 0, remote: 0 });
    endingCallRef.current = false;
    partialUserMessageId.current = null;
    partialAssistantMessageId.current = null;
    setStatus("Connecting");
    try {
      await client.connect({
        webrtcRequestParams: {
          endpoint: `${API_BASE_URL}/api/offer`,
        },
      });
      markConnected();
    } catch (connectionError) {
      let message = await getConnectionErrorMessage(connectionError);
      try {
        await client.disconnect();
      } catch (cleanupError) {
        const cleanupMessage =
          cleanupError instanceof Error
            ? cleanupError.message
            : "The connection could not be closed cleanly.";
        message = `${message} ${cleanupMessage}`;
      }
      setStatus("Error");
      setConnectedAt(null);
      setError(message);
    } finally {
      setIsConnecting(false);
    }
  }

  async function disconnect(closeAfter = false) {
    if (!client || isEnding) {
      return;
    }

    setIsEnding(true);
    setError("");
    endingCallRef.current = true;
    try {
      await client.disconnect();
      markDisconnected();
      void onAppointmentChange();
      if (closeAfter) {
        animateClose();
      }
    } catch (disconnectError) {
      endingCallRef.current = false;
      setStatus("Error");
      setError(
        disconnectError instanceof Error
          ? `The call could not be closed cleanly: ${disconnectError.message}`
          : "The call could not be closed cleanly. Try ending it again.",
      );
    } finally {
      endingCallRef.current = false;
      setIsEnding(false);
    }
  }

  async function closeDialog() {
    if (isConnecting || isEnding) {
      setError("Please wait for the call connection to finish before closing.");
      return;
    }
    if (status === "Connected" || status === "Error") {
      await disconnect(true);
      return;
    }
    animateClose();
  }

  function toggleMicrophone() {
    try {
      enableMic(!isMicEnabled);
    } catch (micError) {
      setError(
        micError instanceof Error
          ? micError.message
          : "The microphone setting could not be changed.",
      );
    }
  }

  const statusClass = status.toLowerCase();
  const isConnected = status === "Connected";
  const audioLevel = isConnected
    ? Math.max(audioLevels.local, audioLevels.remote)
    : 0;
  const barHeights = [0.35, 0.62, 1, 0.74, 0.48, 0.82, 0.38].map((scale) =>
    Math.round(5 + audioLevel * scale * 28),
  );

  return (
    <div
      className={`dialog-backdrop call-backdrop${isVisible ? " is-visible" : ""}${isClosing ? " is-closing" : ""}`}
      onMouseDown={(event) => {
        if (!isClosing && event.target === event.currentTarget) {
          void closeDialog();
        }
      }}
    >
      <section
        aria-labelledby="voice-dialog-title"
        aria-modal="true"
        className="call-panel"
        role="dialog"
      >
        <header className="call-header">
          <div className="call-brand">
            <span className="call-brand-icon">
              <Icon name="mic" size={18} />
            </span>
            <div>
              <strong>NexovAI</strong>
              <span>VOICE APPOINTMENT DESK</span>
            </div>
          </div>
          <button
            aria-label="Close voice assistant"
            className="icon-button"
            disabled={isConnecting || isEnding}
            onClick={() => void closeDialog()}
            type="button"
          >
            <Icon name="close" size={19} />
          </button>
        </header>

        <div className="call-identity">
          <div
            className={`call-avatar${isConnected ? " call-avatar-active" : ""}`}
          >
            <div
              aria-label="Live microphone and assistant audio level"
              className="call-audio-bars"
              role="img"
            >
              {barHeights.map((height, index) => (
                <span key={index} style={{ height: `${height}px` }} />
              ))}
            </div>
          </div>
          <h2 id="voice-dialog-title">Appointment receptionist</h2>
          <p>
            {isConnected
              ? "Your call is connected. You can speak naturally."
              : status === "Connecting"
                ? "Connecting securely to the voice assistant…"
                : status === "Error"
                  ? "The call could not be connected."
                    : status === "Ended"
                      ? "The call has ended. You can start another one."
                  : "Ask about doctors, available times, or appointments."}
          </p>
          <div className={`call-status call-status-${statusClass}`}>
            <span className="call-status-dot" />
            <span role="status">{status}</span>
          </div>
          <time className="call-timer" aria-label="Call duration">
            {formatDuration(elapsedSeconds)}
          </time>
        </div>

        {error && (
          <p className="call-error" role="alert">
            <Icon name="alert" size={16} />
            <span>{error}</span>
          </p>
        )}

        <section
          aria-label="Live conversation transcript"
          aria-live="polite"
          className="call-transcript"
          ref={transcriptRef}
          role="log"
        >
          {messages.length === 0 ? (
            <div className="call-transcript-empty">
              <Icon name="mic" size={19} />
              <span>
                {isConnected
                  ? "The receptionist is ready. Say hello to begin."
                  : "Your live conversation will appear here."}
              </span>
            </div>
          ) : (
            <ol>
              {messages.map((message) => (
                <li
                  className={`call-message call-message-${message.speaker}`}
                  key={message.id}
                >
                  <div className="call-message-meta">
                    <strong>
                      {message.speaker === "user" ? "You" : "NexovAI"}
                    </strong>
                    <time dateTime={message.timestamp}>
                      {formatClock(message.timestamp)}
                    </time>
                  </div>
                  <p>{message.text}</p>
                </li>
              ))}
            </ol>
          )}
        </section>

        <footer className="call-controls">
          {isConnected ? (
            <>
              <button
                aria-pressed={!isMicEnabled}
                className={`call-control-button${!isMicEnabled ? " is-muted" : ""}`}
                onClick={toggleMicrophone}
                type="button"
              >
                <span className="call-control-icon">
                  <Icon name={isMicEnabled ? "mic" : "micOff"} size={19} />
                </span>
                <span>{isMicEnabled ? "Mute" : "Unmute"}</span>
              </button>
              <button
                className="call-end-button"
                disabled={isEnding}
                onClick={() => void disconnect()}
                type="button"
              >
                <Icon name="phone" size={18} />
                {isEnding ? "Ending call…" : "End call"}
              </button>
            </>
          ) : (
            <button
              className="call-start-button"
              disabled={isConnecting || isEnding}
              onClick={() => void connect()}
              type="button"
            >
              <Icon name="phone" size={18} />
              {isConnecting
                ? "Connecting…"
                : status === "Ended"
                  ? "Call again"
                  : "Start call"}
            </button>
          )}
          {!isConnected && (
            <button
              className="call-close-button"
              disabled={isConnecting || isEnding}
              onClick={() => void closeDialog()}
              type="button"
            >
              Close
            </button>
          )}
        </footer>
        <p className="call-security-note">
          <Icon name="check" size={14} />
          Your call connects to the NexovAI voice service.
        </p>
      </section>
    </div>
  );
}

export default VoiceAssistantDialog;
