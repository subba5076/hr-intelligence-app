import ChatWindow from "./components/ChatWindow";
import Sidebar from "./components/Sidebar";
import "./App.css";

export default function App() {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="app-main">
        <ChatWindow />
      </main>
    </div>
  );
}
