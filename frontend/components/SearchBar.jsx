import { useState } from "react";
import { motion } from "framer-motion";
import { Search, Sparkles, Loader2 } from "lucide-react";

export default function SearchBar({ onSearch, loading }) {
	const [domain, setDomain] = useState("");
	const [firstName, setFirstName] = useState("");
	const [lastName, setLastName] = useState("");

	const handleSubmit = (e) => {
		e.preventDefault();
		if (!domain) return;
		onSearch({ domain: domain.trim(), firstName: firstName.trim(), lastName: lastName.trim() });
	};

	return (
		<motion.form
			onSubmit={handleSubmit}
			className="panel fade-in"
			initial={{ opacity: 0, y: 12 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.28 }}
		>
			<div className="panel-header">
				<div className="card-row">
					<div className="badge">
						<Sparkles size={16} />
						Search
					</div>
					<strong>Find deliverable emails</strong>
				</div>
				<div className="badge">
					Pattern + SMTP aware
				</div>
			</div>

			<div className="panel-body stack">
				<div className="input-row" style={{ gridTemplateColumns: "2fr 1fr 1fr" }}>
					<input
						className="input"
						placeholder="Target domain (e.g. stripe.com)"
						value={domain}
						onChange={(e) => setDomain(e.target.value)}
						required
					/>
					<input
						className="input"
						placeholder="First name (optional)"
						value={firstName}
						onChange={(e) => setFirstName(e.target.value)}
					/>
					<input
						className="input"
						placeholder="Last name (optional)"
						value={lastName}
						onChange={(e) => setLastName(e.target.value)}
					/>
				</div>

				<div className="flex-between">
					<span className="helper">We crawl, infer patterns, and verify syntax in one pass.</span>
					<button className="btn primary" type="submit" disabled={loading}>
						{loading ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
						{loading ? "Scanning" : "Search domain"}
					</button>
				</div>
			</div>
		</motion.form>
	);
}
