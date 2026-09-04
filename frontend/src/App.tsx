import { useRoute } from "./lib/router";
import { Hero } from "./components/Hero";
import { About } from "./components/About";
import { LiveStats } from "./components/LiveStats";
import { Features } from "./components/Features";
import { Waitlist } from "./components/Waitlist";
import { Footer } from "./components/Footer";
import { Console } from "./components/Console";

export default function App() {
  const route = useRoute();
  const isConsole = route.startsWith("/dashboard");

  if (isConsole) return <Console />;

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
