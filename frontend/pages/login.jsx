import { useState } from "react";
import { useRouter } from "next/router";
import { motion } from "framer-motion";
import { login, signup, setAuthTokens } from "../utils/api";
import { ShieldCheck, ArrowLeft, ArrowRight } from "lucide-react";

export default function LoginPage() {
	const router = useRouter();
	const [mode, setMode] = useState("login");
	const [form, setForm] = useState({ email: "", password: "", name: "", company: "" });
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState("");

	const handleSubmit = async (e) => {
		e.preventDefault();
		setLoading(true);
		setError("");

		// Client-side validation
		if (mode === "signup") {
			if (!form.name || form.name.trim().length < 2) {
				setError("Name must be at least 2 characters");
				setLoading(false);
				return;
			}
		}
		if (!form.password || form.password.length < 8) {
			setError("Password must be at least 8 characters");
			setLoading(false);
			return;
		}

		try {
			const action = mode === "login" ? login : signup;
			const payload = { email: form.email.trim(), password: form.password };
			if (mode === "signup") {
				payload.name = form.name.trim();
				if (form.company && form.company.trim()) {
					payload.company = form.company.trim();
				}
			}
			const tokens = await action(payload);
			setAuthTokens(tokens);
			router.push("/dashboard");
		} catch (err) {
			// Parse validation errors from backend
			let errorMessage = err.message || "Authentication failed";
			if (errorMessage.includes("string_too_short") || errorMessage.includes("at least")) {
				errorMessage = "Please check all fields meet minimum length requirements";
			} else if (errorMessage.includes("already registered")) {
				errorMessage = "This email is already registered. Try logging in.";
			}
			setError(errorMessage);
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="layout-narrow">
			<button className="btn ghost" type="button" onClick={() => router.push("/")}> 
				<ArrowLeft size={16} /> Back
			</button>

			<motion.div
				className="form-card"
				initial={{ opacity: 0, y: 12 }}
				animate={{ opacity: 1, y: 0 }}
			>
				<div className="card-row" style={{ justifyContent: "space-between" }}>
					<div>
						<div className="kicker">Secure console</div>
						<h2 style={{ margin: "6px 0" }}>{mode === "login" ? "Welcome back" : "Create your workspace"}</h2>
						<p className="small">Access Apollo with JWT-secured API calls.</p>
					</div>
					<div className="brand-mark">AI</div>
				</div>

				<div className="badge" style={{ marginTop: 12 }}>
					<ShieldCheck size={16} /> Sessions stored client-side only.
				</div>

				<form className="stack" style={{ marginTop: 18 }} onSubmit={handleSubmit}>
					{mode === "signup" && (
						<>
							<input
								className="input"
								placeholder="Full name (min 2 characters)"
								value={form.name}
								onChange={(e) => setForm({ ...form, name: e.target.value })}
								minLength={2}
								required
							/>
							<input
								className="input"
								placeholder="Company"
								value={form.company}
								onChange={(e) => setForm({ ...form, company: e.target.value })}
							/>
						</>
					)}

					<input
						className="input"
						type="email"
						placeholder="Work email"
						value={form.email}
						onChange={(e) => setForm({ ...form, email: e.target.value })}
						required
					/>
					<input
						className="input"
						type="password"
						placeholder="Password (min 8 characters)"
						value={form.password}
						onChange={(e) => setForm({ ...form, password: e.target.value })}
						minLength={8}
						required
					/>

					{error && <div className="badge danger">{error}</div>}

					<button className="btn primary" type="submit" disabled={loading}>
						{loading ? "Working..." : mode === "login" ? "Sign in" : "Create account"}
						<ArrowRight size={16} />
					</button>
				</form>

				<div className="flex-between" style={{ marginTop: 14 }}>
					<span className="small">{mode === "login" ? "No account yet?" : "Already onboard?"}</span>
					<button
						className="btn ghost"
						type="button"
						onClick={() => setMode(mode === "login" ? "signup" : "login")}
					>
						Switch to {mode === "login" ? "Sign up" : "Log in"}
					</button>
				</div>
			</motion.div>
		</div>
	);
}
