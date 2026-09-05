import { useRoute } from "./lib/router";
import { Hero } from "./components/Hero";
import { About } from "./components/About";
import { LiveStats } from "./components/LiveStats";
import { Features } from "./components/Features";
import { Waitlist } from "./components/Waitlist";
import { Footer } from "./components/Footer";
import { Console } from "./components/Console";
import { LoginScreen } from "./components/LoginScreen";
import { AuthCallback } from "./components/AuthCallback";
import { FeaturesPage } from "./components/FeaturesPage";
import { GuardrailsPage } from "./components/GuardrailsPage";
import { ResourcesPage } from "./components/ResourcesPage";
import { ApiReferencePage } from "./components/ApiReferencePage";
import { TutorialPage } from "./components/TutorialPage";
import { ExtensionPage } from "./components/ExtensionPage";
import { ArchitecturePage } from "./components/ArchitecturePage";
import { ChangelogPage } from "./components/ChangelogPage";

export default function App() {
  const route = useRoute();

  if (route.startsWith("/auth/callback")) return <AuthCallback />;
  if (route.startsWith("/login")) return <LoginScreen />;
  if (route.startsWith("/dashboard")) return <Console />;
  if (route.startsWith("/features")) return <FeaturesPage />;
  if (route.startsWith("/guardrails")) return <GuardrailsPage />;
  if (route.startsWith("/resources")) return <ResourcesPage />;
  if (route.startsWith("/api")) return <ApiReferencePage />;
  if (route.startsWith("/tutorial")) return <TutorialPage />;
  if (route.startsWith("/extension")) return <ExtensionPage />;
  if (route.startsWith("/architecture")) return <ArchitecturePage />;
  if (route.startsWith("/changelog")) return <ChangelogPage />;

  return (
    <main className="bg-black min-h-screen">
      <Hero />
      <About />
      <LiveStats />
      <Features />
      <Waitlist />
      <Footer />
    </main>
  );
}
