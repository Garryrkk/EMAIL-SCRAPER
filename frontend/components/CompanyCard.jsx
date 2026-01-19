import { motion } from "framer-motion";
import { Building2, ShieldCheck, Radar, Activity, RefreshCw } from "lucide-react";

export default function CompanyCard({ company }) {
	if (!company) return null;

	return (
		<motion.div
			className="panel fade-in"
			initial={{ opacity: 0, y: 8 }}
			animate={{ opacity: 1, y: 0 }}
		>
			<div className="panel-header">
				<div className="card-row">
					<div className="brand-mark" style={{ width: 32, height: 32, fontSize: 13 }}>
						{company.domain?.slice(0, 2)?.toUpperCase()}
					</div>
					<div>
						<div className="kicker">Company</div>
						<strong>{company.name || company.domain}</strong>
					</div>
				</div>
				<div className="badge success">
					<ShieldCheck size={16} />
					{company.is_verified ? "Verified" : "Tracked"}
				</div>
			</div>

			<div className="panel-body stat-grid">
				<div className="stat">
					<div>
						<div className="small">Domain</div>
						<strong>{company.domain}</strong>
					</div>
					<Building2 size={20} color="#9da7c2" />
				</div>
				<div className="stat">
					<div>
						<div className="small">Pattern</div>
						<strong>{company.detected_pattern || "Pending"}</strong>
						<div className="small">Confidence {Math.round((company.pattern_confidence || 0) * 100)}%</div>
					</div>
					<Radar size={20} color="#9da7c2" />
				</div>
				<div className="stat">
					<div>
						<div className="small">Emails indexed</div>
						<strong>{company.email_count ?? company.public_emails_count ?? 0}</strong>
						<div className="small">Bounce rate {Math.round((company.bounce_rate || 0) * 100)}%</div>
					</div>
					<Activity size={20} color="#9da7c2" />
				</div>
				<div className="stat">
					<div>
						<div className="small">Last scan</div>
						<strong>{company.last_crawled_at ? new Date(company.last_crawled_at).toLocaleDateString() : "Not yet"}</strong>
						<div className="small">Confidence {Math.round((company.confidence_score || 0) * 100)}%</div>
					</div>
					<RefreshCw size={20} color="#9da7c2" />
				</div>
			</div>
		</motion.div>
	);
}
