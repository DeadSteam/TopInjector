/** @type {import('tailwindcss').Config} */
export default {
	content: ["./src/**/*.{html,js,svelte,ts}"],
	theme: {
		extend: {
			colors: {
				// used by `@apply border-border` in app.css
				border: "#e5e7eb",
			},
		},
	},
	plugins: [],
};
