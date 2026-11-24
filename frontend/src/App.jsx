import { useCallback, useEffect, useRef, useState } from "react";

import AppointmentUpdateCard from "./components/AppointmentUpdateCard.jsx";
import ErrorState from "./components/ErrorState.jsx";
import Sidebar from "./components/Sidebar.jsx";
import Topbar from "./components/Topbar.jsx";
import VoiceAssistantDialog from "./components/VoiceAssistantDialog.jsx";
import AppointmentsPage from "./pages/AppointmentsPage.jsx";
import AvailabilityPage from "./pages/AvailabilityPage.jsx";
import DoctorsPage from "./pages/DoctorsPage.jsx";
import OverviewPage from "./pages/OverviewPage.jsx";
import {
  cancelAppointment,
  findRecentAppointmentChange,
  getDashboardData,
} from "./services/api.js";

const pageDetails = {
  overview: {
    title: "Overview",
    subtitle: "A thoughtful view of your clinic, at a glance.",
  },
  doctors: {
    title: "Doctors",
    subtitle: "The specialists caring for your patients.",
  },
  appointments: {
    title: "Appointments",
    subtitle: "A clear record of every patient visit.",
  },
  availability: {
    title: "Availability",
    subtitle: "Open times and confirmed visits across your clinic.",
  },
};

function App() {
  const [activePage, setActivePage] = useState("overview");
  const [voiceAssistantOpen, setVoiceAssistantOpen] = useState(false);
  const [data, setData] = useState({
    doctors: [],
    appointments: [],
    slots: [],
  });
  const dataRef = useRef({ doctors: [], appointments: [], slots: [] });
  const hasLoadedDataRef = useRef(false);
  const [recentAction, setRecentAction] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [pendingCancelId, setPendingCancelId] = useState(null);
  const [cancellingId, setCancellingId] = useState(null);
  const [actionError, setActionError] = useState("");

  const refreshData = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const nextData = await getDashboardData();
      if (hasLoadedDataRef.current) {
        const change = findRecentAppointmentChange(
          dataRef.current.appointments,
          nextData.appointments,
        );
        if (change) {
          setRecentAction(change);
        }
      }
      dataRef.current = nextData;
      hasLoadedDataRef.current = true;
      setData(nextData);
    } catch (error) {
      setLoadError(
        error instanceof Error
          ? error.message
          : "An unexpected API error occurred.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshData();
  }, [refreshData]);

  async function confirmCancellation(appointment) {
    setCancellingId(appointment.id);
    setActionError("");
    try {
      await cancelAppointment(appointment.phone_number, appointment.id);
      setPendingCancelId(null);
      await refreshData();
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "The appointment could not be cancelled.",
      );
    } finally {
      setCancellingId(null);
    }
  }

  const page = pageDetails[activePage];

  function renderPage() {
    if (activePage === "doctors") {
      return <DoctorsPage doctors={data.doctors} loading={loading} />;
    }
    if (activePage === "appointments") {
      return (
        <AppointmentsPage
          actionError={actionError}
          appointments={data.appointments}
          cancellingId={cancellingId}
          loading={loading}
          recentAction={recentAction}
          onCancel={(id) => {
            setActionError("");
            setPendingCancelId(id);
          }}
          onConfirmCancel={confirmCancellation}
          onKeepAppointment={() => setPendingCancelId(null)}
          pendingId={pendingCancelId}
        />
      );
    }
    if (activePage === "availability") {
      return (
        <AvailabilityPage
          doctors={data.doctors}
          loading={loading}
          slots={data.slots}
        />
      );
    }
    return (
      <OverviewPage
        appointments={data.appointments}
        availableSlots={data.slots.filter((slot) => !slot.is_booked)}
        doctors={data.doctors}
        loading={loading}
        onNavigate={setActivePage}
        onTryVoice={() => setVoiceAssistantOpen(true)}
        recentAction={recentAction}
      />
    );
  }

  return (
    <div className="app-shell">
      <Sidebar activePage={activePage} onNavigate={setActivePage} />
      <main className="main-panel">
        <Topbar
          onRefresh={refreshData}
          refreshing={loading}
          subtitle={page.subtitle}
          title={page.title}
        />
        {recentAction && !loadError && (
          <div className="appointment-update-wrap">
            <AppointmentUpdateCard
              onDismiss={() => setRecentAction(null)}
              update={recentAction}
            />
          </div>
        )}
        {loadError ? (
          <div className="page-content">
            <ErrorState message={loadError} onRetry={refreshData} />
          </div>
        ) : (
          renderPage()
        )}
      </main>
      {voiceAssistantOpen && (
        <VoiceAssistantDialog
          onAppointmentChange={refreshData}
          onClose={() => setVoiceAssistantOpen(false)}
        />
      )}
    </div>
  );
}

export default App;
