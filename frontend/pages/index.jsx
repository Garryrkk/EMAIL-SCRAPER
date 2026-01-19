import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Search, MailCheck, ShieldHalf, ArrowRight } from "lucide-react";
import { getAccessToken } from "../utils/api";

export default function Home() {
	const [hasSession, setHasSession] = useState(false);

	useEffect(() => {
		setHasSession(Boolean(getAccessToken()));
	}, []);

	return (
		<div>
			<header className="navbar">
				<div className="brand">
					<div className="brand-mark">AI</div>
					Apollo Intelligence
				</div>
				<div className="nav-actions">
					<Link href={hasSession ? "/dashboard" : "/login"} className="btn ghost">
						{hasSession ? "Go to app" : "Log in"}
					</Link>
					<Link href="/login" className="btn primary">
						Launch console
						<ArrowRight size={16} />
					</Link>
				</div>
			</header>

			<section className="hero">
				<div className="hero-card">
					<div className="hero-card-content">
						<div className="badge">Precision email OS</div>
						<h1 className="hero-title">Discover, verify, and ship emails without the noise.</h1>
						<p className="hero-subtitle">
							Apollo scans domains, infers patterns, runs SMTP checks, and tracks deliverability so your teams can reach the right people with confidence.
						</p>
						<div className="pills">
							<span className="pill"><Search size={16} /> Domain intelligence</span>
							<span className="pill"><MailCheck size={16} /> SMTP verification</span>
							<span className="pill"><ShieldHalf size={16} /> Risk-aware scoring</span>
						</div>
						<div style={{ display: "flex", gap: 12 }}>
							<Link href="/dashboard" className="btn primary">
								Enter dashboard
								<ArrowRight size={16} />
							</Link>
							<Link href="/login" className="btn">
								Create account
							</Link>
						</div>
					</div>
				</div>

				<motion.div
					className="panel"
					initial={{ opacity: 0, y: 20 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ delay: 0.1 }}
					style={{ padding: 24 }}
				>
					<div className="panel-header" style={{ borderBottom: "none" }}>
						<div>
							<div className="kicker">Live signals</div>
							<strong>What you get in the console</strong>
						</div>
					</div>
					<div className="stat-grid">
						{["Pattern inference", "SMTP safe-check", "Bounce tracking", "Export-ready"]
							.map((item) => (
								<div key={item} className="stat" style={{ minHeight: 110 }}>
									<div>
										<div className="small">Capability</div>
										<strong>{item}</strong>
										<div className="small">Fast, deterministic, audit friendly.</div>
									</div>
								</div>
							))}
					</div>
				</motion.div>
			</section>
		</div>
	);
}
