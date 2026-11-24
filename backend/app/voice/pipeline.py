import os

import aiohttp
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import (
    PipelineParams,
    PipelineWorker,
    ProcessorUnusablePolicy,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frameworks.rtvi import RTVIObserverParams
from pipecat.services.elevenlabs.stt import ElevenLabsSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.workers.runner import WorkerRunner

from app.voice.tools import AppointmentTools


SYSTEM_PROMPT = """
You are a polite hospital receptionist speaking with a patient.
Greet the patient warmly and ask how you can help. Use the appointment tools
for availability, bookings, and cancellations; never invent doctors, slots,
or results. Ask for the patient's phone number and require it to be spoken
digit by digit. Read the full number back and ask whether it is correct before
booking or cancelling. For a booking, first confirm the exact doctor and slot
using the date in YYYY-MM-DD format and time in HH:MM format, then wait for an
explicit yes before calling the booking tool again. For a cancellation, state
the exact appointment details, ask whether to cancel, and wait for an explicit
yes before calling the cancellation tool again. If a tool says confirmation
is required, ask its question and do not claim the action is complete. Never
state that an appointment is booked or cancelled unless the tool returned
success as true. Ask
brief follow-up questions when information is missing. Speak naturally and
keep replies concise. Do not provide medical diagnosis or treatment advice;
offer to connect the patient with qualified medical staff for medical concerns.
""".strip()


REQUIRED_ENV_VARS = (
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_VOICE_ID",
    "GOOGLE_API_KEY",
)


def missing_voice_settings() -> list[str]:
    return [
        name
        for name in REQUIRED_ENV_VARS
        if not os.getenv(name, "").strip()
    ]


async def run_voice_pipeline(connection: SmallWebRTCConnection) -> None:
    logger.info("Starting voice pipeline for peer {}", connection.pc_id)

    try:
        async with aiohttp.ClientSession() as session:
            transport = SmallWebRTCTransport(
                webrtc_connection=connection,
                params=TransportParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                ),
            )

            stt = ElevenLabsSTTService(
                api_key=os.environ["ELEVENLABS_API_KEY"],
                aiohttp_session=session,
            )
            llm = GoogleLLMService(
                api_key=os.environ["GOOGLE_API_KEY"],
                settings=GoogleLLMService.Settings(
                    model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
                    system_instruction=SYSTEM_PROMPT,
                ),
            )
            tts = ElevenLabsTTSService(
                api_key=os.environ["ELEVENLABS_API_KEY"],
                settings=ElevenLabsTTSService.Settings(
                    voice=os.environ["ELEVENLABS_VOICE_ID"],
                ),
            )

            appointment_tools = AppointmentTools()
            context = LLMContext(tools=appointment_tools.get_tools())
            user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
                context,
                user_params=LLMUserAggregatorParams(
                    vad_analyzer=SileroVADAnalyzer(),
                ),
            )

            pipeline = Pipeline(
                [
                    transport.input(),
                    stt,
                    user_aggregator,
                    llm,
                    tts,
                    transport.output(),
                    assistant_aggregator,
                ]
            )
            worker = PipelineWorker(
                pipeline,
                params=PipelineParams(
                    enable_metrics=True,
                    enable_usage_metrics=True,
                ),
                rtvi_observer_params=RTVIObserverParams(),
                processor_unusable_policy=ProcessorUnusablePolicy.END,
            )
            runner = WorkerRunner(handle_sigint=False)
            await runner.add_workers(worker)

            @transport.event_handler("on_client_connected")
            async def on_client_connected(_transport, _client) -> None:
                logger.info("Voice client connected")
                context.add_message(
                    {
                        "role": "developer",
                        "content": "Greet the patient and ask what they need help with.",
                    }
                )
                await worker.queue_frames([LLMRunFrame()])

            @transport.event_handler("on_client_disconnected")
            async def on_client_disconnected(_transport, _client) -> None:
                logger.info("Voice client disconnected")
                await runner.cancel()

            await runner.run()
    except Exception:
        logger.exception("Voice pipeline failed for peer {}", connection.pc_id)
        raise
    finally:
        logger.info("Voice pipeline stopped for peer {}", connection.pc_id)
