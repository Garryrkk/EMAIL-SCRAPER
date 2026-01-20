import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { motion } from "framer-motion";
import {
	getAccessToken,
	getProfile,
	getCredits,
	searchDomain,
	verifyEmail,
	getCompany,
	clearTokens,
} from "../utils/api";
import SearchBar from "../components/SearchBar";
import CompanyCard from "../components/CompanyCard";
import EmailRow from "../components/EmailRow";
import {
	User,
	LogOut,
	MailCheck,
	ShieldHalf,
	Zap,
	Cpu,
	ArrowRight,
} from "lucide-react";

export default function Dashboard() {
	const router = useRouter();
	const [user, setUser] = useState(null);
	const [credits, setCredits] = useState(null);
	const [company, setCompany] = useState(null);
	const [results, setResults] = useState([]);
	const [searching, setSearching] = useState(false);
	const [verifying, setVerifying] = useState(false);
	const [verifyPayload, setVerifyPayload] = useState({ email: "", domain: "" });
	const [verifyResult, setVerifyResult] = useState(null);
	const [error, setError] = useState("");

	useEffect(() => {
		if (!getAccessToken()) {
			router.replace("/login");
			return;
		}

		const bootstrap = async () => {
			try {
				const [profile, creditInfo] = await Promise.all([getProfile(), getCredits()]);
				setUser(profile);
				setCredits(creditInfo);
			} catch (err) {
				setError(err.message || "Unable to load profile");
			}
		};

		bootstrap();
	}, [router]);

	const handleSearch = async ({ domain }) => {
		setSearching(true);
		setError("");
		setCompany(null);
		setResults([]);
		try {
			const res = await searchDomain(domain);
			setResults(res.emails || []);
			try {
				const companyData = await getCompany(domain);
				setCompany(companyData);
				setVerifyPayload((prev) => ({ ...prev, domain }));
			} catch (_) {
				// Company may not exist yet; keep silent
			}
		} catch (err) {
			setError(err.message || "Search failed");
		} finally {
			setSearching(false);
		}
	};

	const handleVerify = async (e) => {
		e.preventDefault();
		if (!verifyPayload.email || !verifyPayload.domain) return;
		setVerifying(true);
		setVerifyResult(null);
		setError("");
		try {
			const res = await verifyEmail(verifyPayload);
			setVerifyResult(res);
		} catch (err) {
			setError(err.message || "Verification failed");
		} finally {
			setVerifying(false);
		}
	};

	const signOut = () => {
		clearTokens();
		router.replace("/login");
	};

	return (
		<div>
			<header className="navbar">
				<div className="brand">
					<div className="brand-mark">AI</div>
					Apollo Console
				</div>
				<div className="nav-actions">
					{user && (
						<span className="badge">
							<User size={14} /> {user.email}
						</span>
					)}
					<button className="btn ghost" onClick={signOut}>
						<LogOut size={16} />
						Sign out
					</button>
				</div>
			</header>

			<main className="section" style={{ paddingTop: 12 }}>
				<div className="stat-grid">
					<div className="stat">
						<div>
							<div className="small">Plan</div>
							<strong>{user?.plan || "-"}</strong>
							<div className="small">Status {user?.status || "loading"}</div>
						</div>
						<Zap size={20} color="#9da7c2" />
					</div>
					<div className="stat">
						<div>
							<div className="small">Credits</div>
							<strong>{credits?.credits ?? "-"}</strong>
							<div className="small">Monthly limit {credits?.monthly_limit ?? "-"}</div>
						</div>
						<Cpu size={20} color="#9da7c2" />
					</div>
					<div className="stat">
						<div>
							<div className="small">Verification</div>
							<strong>SMTP + syntax</strong>
							<div className="small">Risk score aware</div>
						</div>
						<ShieldHalf size={20} color="#9da7c2" />
					</div>
					<div className="stat">
						<div>
							<div className="small">Exports</div>
							<strong>CSV ready</strong>
							<div className="small">Sorting by confidence</div>
						</div>
						<MailCheck size={20} color="#9da7c2" />
					</div>
				</div>

				<SearchBar onSearch={handleSearch} loading={searching} />

				{error && <div className="badge danger">{error}</div>}

				{company && <CompanyCard company={company} />}

				<div className="grid">
					<motion.div className="panel" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
						<div className="panel-header">
							<div className="card-row">
								<div className="badge">Live results</div>
								<strong>Emails</strong>
							</div>
							<span className="small">Sorted by confidence</span>
						</div>
						<div className="panel-body" style={{ overflowX: "auto" }}>
							{results.length === 0 ? (
								<div className="small">Run a domain search to see results.</div>
							) : (
								<table className="table">
									<thead>
										<tr>
											<th>Email</th>
											<th>Source</th>
											<th>Confidence</th>
											<th>Status</th>
										</tr>
									</thead>
									<tbody>
										{results.map((email) => (
											<EmailRow key={email.email || email.id} email={email} />
										))}
									</tbody>
								</table>
							)}
						</div>
					</motion.div>

					<motion.div className="panel" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
						<div className="panel-header">
							<div className="card-row">
								<div className="badge">Verify</div>
								<strong>Check a single email</strong>
							</div>
						</div>
						<div className="panel-body stack">
							<form className="stack" onSubmit={handleVerify}>
								<input
									className="input"
									placeholder="Email to verify"
									value={verifyPayload.email}
									onChange={(e) => setVerifyPayload({ ...verifyPayload, email: e.target.value })}
									required
								/>
								<input
									className="input"
									placeholder="Domain"
									value={verifyPayload.domain}
									onChange={(e) => setVerifyPayload({ ...verifyPayload, domain: e.target.value })}
									required
								/>
								<button className="btn primary" type="submit" disabled={verifying}>
									{verifying ? "Checking" : "Verify"}
									<ArrowRight size={16} />
								</button>
							</form>

							{verifyResult && (
								<div className="badge success">
									<ShieldHalf size={16} /> {verifyResult.email} • {verifyResult.status} •
									Confidence {Math.round((verifyResult.confidence || 0) * 100)}%
								</div>
							)}
						</div>
					</motion.div>
				</div>
			</main>
		</div>
	);
}
