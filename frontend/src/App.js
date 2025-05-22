import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, Link, useLocation, NavLink } from 'react-router-dom';
import { Container, Nav } from 'react-bootstrap';
import 'bootstrap/dist/css/bootstrap.min.css';


import Home from './components/Home';
import KeyChecker from './components/KeyChecker';
import BatchCheck from './components/BatchCheck';
import AccountManagement from './components/AccountManagement';
import VPNSettings from './components/VPNSettings';


const AnimatedRoutes = () => {
  const location = useLocation();
  const [displayLocation, setDisplayLocation] = useState(location);
  const [transitionStage, setTransitionStage] = useState("page-transition-enter");

  useEffect(() => {
    if (location !== displayLocation) {
      setTransitionStage("page-transition-exit");
    }
  }, [location, displayLocation]);

  const handleAnimationEnd = () => {
    if (transitionStage === "page-transition-exit") {
      setTransitionStage("page-transition-enter");
      setDisplayLocation(location);
    }
  };

  return (
    <div 
      className={`${transitionStage}`}
      onAnimationEnd={handleAnimationEnd}
    >
      <Routes location={displayLocation}>
        <Route path="/" element={<Home />} />
        <Route path="/check" element={<KeyChecker />} />
        <Route path="/batch" element={<BatchCheck />} />
        <Route path="/accounts" element={<AccountManagement />} />
        <Route path="/vpn" element={<VPNSettings />} />
      </Routes>
    </div>
  );
};

function App() {
  return (
    <Router>
      <div className="App">
        <header className="modern-header">
          <Container>
            <nav className="modern-nav">
              <div className="d-flex justify-content-between align-items-center p-3">
                <div className="logo">
                  <Link to="/" className="navbar-brand fw-bold text-primary">Microsoft Key Checker</Link>
                </div>
                <Nav className="d-flex">
                  <Nav.Link as={NavLink} to="/" className={({ isActive }) => isActive ? 'modern-nav-link active ripple' : 'modern-nav-link ripple'} end>Главная</Nav.Link>
                  <Nav.Link as={NavLink} to="/check" className={({ isActive }) => isActive ? 'modern-nav-link active ripple' : 'modern-nav-link ripple'}>Проверка ключа</Nav.Link>
                  <Nav.Link as={NavLink} to="/batch" className={({ isActive }) => isActive ? 'modern-nav-link active ripple' : 'modern-nav-link ripple'}>Пакетная проверка</Nav.Link>
                  <Nav.Link as={NavLink} to="/accounts" className={({ isActive }) => isActive ? 'modern-nav-link active ripple' : 'modern-nav-link ripple'}>Управление аккаунтами</Nav.Link>
                  <Nav.Link as={NavLink} to="/vpn" className={({ isActive }) => isActive ? 'modern-nav-link active ripple' : 'modern-nav-link ripple'}>Настройки VPN</Nav.Link>
                </Nav>
              </div>
            </nav>
          </Container>
        </header>

        <main className="app-container">
          <Container className="mt-4">
            <AnimatedRoutes />
          </Container>
        </main>
      </div>
    </Router>
  );
}

export default App;
