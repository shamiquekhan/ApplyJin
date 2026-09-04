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

export default function App() {
  const route = useRoute();

  if (route.startsWith("/auth/callback")) return <AuthCallback />;
  if (route.startsWith("/login")) return <LoginScreen />;
  if (route.startsWith("/dashboard")) return <Console />;

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
