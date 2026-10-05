import { Logo } from "./components/Icons";
import { ToastProvider } from "./components/Toast";
import { useHashPath } from "./lib/router";
import { LibraryPage } from "./pages/Library";
import { RecordingPage } from "./pages/Recording";
import { RubricsPage } from "./pages/Rubrics";

export default function App() {
  const path = useHashPath();
  const m = path.match(/^\/r\/([\w-]+)/);
  const section = m ? "lib" : path.startsWith("/rubrics") ? "rub" : "lib";
  return (
    <ToastProvider>
      <header className="topbar">
        <a className="brand" href="#/"><Logo />DeutschAutoCorrect</a>
        <nav className="nav" aria-label="Navigation principale">
          <a href="#/" className={section === "lib" ? "active" : ""}>Enregistrements</a>
          <a href="#/rubrics" className={section === "rub" ? "active" : ""}>Barèmes</a>
        </nav>
      </header>
      <main>
        {m ? <RecordingPage key={m[1]} id={m[1]} /> : path.startsWith("/rubrics") ? <RubricsPage /> : <LibraryPage />}
      </main>
    </ToastProvider>
  );
}
