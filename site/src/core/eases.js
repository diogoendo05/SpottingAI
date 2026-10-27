// Curvas da §2.4, registradas uma vez para a timeline e para a UI.
import gsap from "gsap";
import { CustomEase } from "gsap/CustomEase";

gsap.registerPlugin(CustomEase);
CustomEase.create("outStrong", "M0,0 C0.23,1 0.32,1 1,1");
CustomEase.create("inOutStrong", "M0,0 C0.77,0 0.175,1 1,1");
