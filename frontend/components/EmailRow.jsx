import { ShieldCheck, AlertTriangle, HelpCircle } from "lucide-react";

const statusStyles = {
	valid: { label: "Valid", className: "badge success" },
	invalid: { label: "Invalid", className: "badge danger" },
	accept_all: { label: "Accept-all", className: "badge warning" },
	unknown: { label: "Unknown", className: "badge" },
	risky: { label: "Risky", className: "badge warning" },
};

export default function EmailRow({ email }) {
	const status = statusStyles[email.status] || statusStyles.unknown;

	return (
		<tr>
			<td>{email.email || email.address}</td>
			<td>{email.source}</td>
			<td>{Math.round((email.confidence || 0) * 100)}%</td>
			<td>
				<span className={status.className}>
					{email.status === "valid" ? (
						<ShieldCheck size={14} />
					) : email.status === "invalid" ? (
						<AlertTriangle size={14} />
					) : (
						<HelpCircle size={14} />
					)}
					{status.label}
				</span>
			</td>
		</tr>
	);
}
