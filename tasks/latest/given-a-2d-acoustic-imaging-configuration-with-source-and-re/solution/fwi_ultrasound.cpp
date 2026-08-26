#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <map>
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <numeric>

struct JsonValue {
    enum Type { NUL, BOOL, NUMBER, STRING, ARRAY, OBJECT };
    Type type; double num_val; bool bool_val; std::string str_val;
    std::vector<JsonValue> arr_val; std::map<std::string, JsonValue> obj_val;
    JsonValue() : type(NUL), num_val(0), bool_val(false) {}
    double as_double() const { return num_val; }
    int as_int() const { return (int)num_val; }
    bool as_bool() const { return bool_val; }
    const std::string& as_string() const { return str_val; }
    const std::vector<JsonValue>& as_array() const { return arr_val; }
    const std::map<std::string, JsonValue>& as_object() const { return obj_val; }
    bool has(const std::string& k) const { return type==OBJECT && obj_val.count(k); }
    const JsonValue& operator[](const std::string& k) const { return obj_val.at(k); }
    size_t size() const { return type==ARRAY ? arr_val.size() : obj_val.size(); }
};
class JsonParser {
    const std::string& src; size_t pos;
    void skip_ws(){while(pos<src.size()&&(src[pos]==' '||src[pos]=='\t'||src[pos]=='\n'||src[pos]=='\r'))pos++;}
    JsonValue parse_string(){JsonValue v;v.type=JsonValue::STRING;pos++;while(pos<src.size()&&src[pos]!='"'){if(src[pos]=='\\'){pos++;if(pos<src.size()){switch(src[pos]){case'"':v.str_val+='"';break;case'\\':v.str_val+='\\';break;case'n':v.str_val+='\n';break;case't':v.str_val+='\t';break;default:v.str_val+=src[pos];}}}else v.str_val+=src[pos];pos++;}pos++;return v;}
    JsonValue parse_number(){JsonValue v;v.type=JsonValue::NUMBER;size_t s=pos;if(src[pos]=='-')pos++;while(pos<src.size()&&(isdigit(src[pos])||src[pos]=='.'||src[pos]=='e'||src[pos]=='E'||src[pos]=='+'||src[pos]=='-')){if((src[pos]=='+'||src[pos]=='-')&&pos>s&&src[pos-1]!='e'&&src[pos-1]!='E')break;pos++;}v.num_val=std::stod(src.substr(s,pos-s));return v;}
    JsonValue parse_value(){skip_ws();if(pos>=src.size())return JsonValue();
        if(src[pos]=='"')return parse_string();
        if(src[pos]=='{'){JsonValue v;v.type=JsonValue::OBJECT;pos++;skip_ws();if(src[pos]=='}'){pos++;return v;}while(true){skip_ws();auto k=parse_string().str_val;skip_ws();pos++;v.obj_val[k]=parse_value();skip_ws();if(src[pos]=='}'){pos++;break;}pos++;}return v;}
        if(src[pos]=='['){JsonValue v;v.type=JsonValue::ARRAY;pos++;skip_ws();if(src[pos]==']'){pos++;return v;}while(true){v.arr_val.push_back(parse_value());skip_ws();if(src[pos]==']'){pos++;break;}pos++;}return v;}
        if(src.substr(pos,4)=="true"){pos+=4;JsonValue v;v.type=JsonValue::BOOL;v.bool_val=true;return v;}
        if(src.substr(pos,5)=="false"){pos+=5;JsonValue v;v.type=JsonValue::BOOL;v.bool_val=false;return v;}
        if(src.substr(pos,4)=="null"){pos+=4;return JsonValue();}
        return parse_number();}
public:JsonParser(const std::string& s):src(s),pos(0){}JsonValue parse(){return parse_value();}
};
JsonValue parse_json_file(const std::string& path){
    std::ifstream f(path);if(!f.is_open()){std::cerr<<"Cannot open: "<<path<<std::endl;exit(1);}
    std::string c((std::istreambuf_iterator<char>(f)),std::istreambuf_iterator<char>());
    JsonParser p(c);return p.parse();}
double r6(double v){if(std::isnan(v)||std::isinf(v))return 0.0;return std::floor(v*1000000.0+0.5)/1000000.0;}

double ricker_wavelet(double t, double f_mhz, double delay) {
    double tau = t - delay;
    double arg = M_PI * f_mhz * tau;
    double arg2 = arg * arg;
    return (1.0 - 2.0 * arg2) * std::exp(-arg2);
}

double compute_travel_time(int sx, int sz, int rx, int rz, double dx, double avg_vel) {
    double dist = std::sqrt((double)((sx-rx)*(sx-rx) + (sz-rz)*(sz-rz))) * dx;
    return dist / avg_vel * 1000.0;
}

int main(int argc, char* argv[]) {
    if (argc < 2) { std::cerr << "Usage: fwi_ultrasound --config <path> --data-dir <path> --output <path>\n"; return 1; }
    std::string config_path, data_dir, output_path;
    for(int i=1;i<argc;i++){std::string a=argv[i];if(a=="--config"&&i+1<argc)config_path=argv[++i];else if(a=="--data-dir"&&i+1<argc)data_dir=argv[++i];else if(a=="--output"&&i+1<argc)output_path=argv[++i];}
    if(config_path.empty()||data_dir.empty()||output_path.empty()){std::cerr<<"Missing args\n";return 1;}

    auto settings = parse_json_file(config_path);
    auto src_data = parse_json_file(data_dir + "/sources.json");
    auto rcv_data = parse_json_file(data_dir + "/receivers.json");
    auto obs_data = parse_json_file(data_dir + "/observed_data.json");

    int nx = settings["grid_nx"].as_int(), nz = settings["grid_nz"].as_int();
    double dx = settings["dx_mm"].as_double(), dt = settings["dt_us"].as_double();
    int nt = settings["num_timesteps"].as_int(), niter = settings["num_inversion_iterations"].as_int();
    double alpha0 = settings["attenuation_alpha0_np_per_mhz_cm"].as_double();
    double atten_n = settings["attenuation_power_n"].as_double();
    double init_vel = settings["initial_velocity_mps"].as_double();
    double step_init = settings["step_length_initial"].as_double();
    double step_red = settings["step_length_reduction"].as_double();

    // Parse sources/receivers
    struct Src { std::string id; int ix, iz; double freq, amp, delay; };
    struct Rcv { std::string id; int ix, iz; };
    std::vector<Src> sources;
    for (auto& s : src_data["sources"].as_array())
        sources.push_back({s["source_id"].as_string(), s["position_ix"].as_int(), s["position_iz"].as_int(),
                          s["peak_frequency_mhz"].as_double(), s["amplitude"].as_double(), s["delay_us"].as_double()});
    std::vector<Rcv> receivers;
    for (auto& r : rcv_data["receivers"].as_array())
        receivers.push_back({r["receiver_id"].as_string(), r["position_ix"].as_int(), r["position_iz"].as_int()});

    // Parse observed data
    int nsrc = obs_data["num_sources"].as_int(), nrcv = obs_data["num_receivers"].as_int();
    std::vector<std::vector<std::vector<double>>> obs(nsrc, std::vector<std::vector<double>>(nrcv, std::vector<double>(nt)));
    for (int s = 0; s < nsrc; s++)
        for (int r = 0; r < nrcv; r++)
            for (int t = 0; t < nt; t++)
                obs[s][r][t] = obs_data["data"].as_array()[s].as_array()[r].as_array()[t].as_double();

    // Forward modeling: compute Ricker wavelets and travel times
    std::vector<std::vector<double>> src_wavelets(nsrc, std::vector<double>(nt));
    std::vector<std::vector<double>> travel_times(nsrc, std::vector<double>(nrcv));
    double avg_vel = init_vel;

    for (int s = 0; s < nsrc; s++) {
        for (int t = 0; t < nt; t++) {
            double time = t * dt;
            src_wavelets[s][t] = ricker_wavelet(time, sources[s].freq, sources[s].delay);
        }
        for (int r = 0; r < nrcv; r++) {
            travel_times[s][r] = compute_travel_time(sources[s].ix, sources[s].iz,
                                                      receivers[r].ix, receivers[r].iz, dx, avg_vel);
        }
    }

    // Attenuation model
    std::vector<double> freq_list;
    for (auto& f : settings["source_frequency_mhz"].as_array()) freq_list.push_back(f.as_double());
    std::sort(freq_list.begin(), freq_list.end());

    struct AttenEntry { double freq, coeff, phase_corr; };
    std::vector<AttenEntry> atten_model;
    for (double f : freq_list) {
        double coeff = alpha0 * std::pow(f, atten_n);
        // Kramers-Kronig: phase velocity correction = c0 * (1 + alpha0/(pi) * f^(n-1) * ln(f/f_ref))
        double phase_corr = (alpha0 / M_PI) * std::pow(f, atten_n - 1.0) * std::log(f / freq_list[0] + 1e-10);
        atten_model.push_back({f, coeff, phase_corr});
    }

    // Simplified inversion: gradient descent on velocity model
    double water_vel = settings["water_velocity_mps"].as_double();
    std::vector<std::vector<double>> current_vel(nz, std::vector<double>(nx, water_vel));
    std::vector<std::vector<double>> hessian_diag(nz, std::vector<double>(nx, 0.0));
    int total_fwd = 0, total_adj = 0;

    struct IterResult { int iter; double misfit, grad_norm, max_grad, step_len; };
    std::vector<IterResult> iter_results;
    double initial_misfit = 0;

    for (int it = 0; it < niter; it++) {
        // Compute misfit and gradient
        double misfit = 0;
        std::vector<std::vector<double>> gradient(nz, std::vector<double>(nx, 0.0));

        for (int s = 0; s < nsrc; s++) {
            total_fwd++;
            // Simplified forward: compute synthetic data using current velocity
            for (int r = 0; r < nrcv; r++) {
                double dist = std::sqrt((double)((sources[s].ix-receivers[r].ix)*(sources[s].ix-receivers[r].ix) +
                             (sources[s].iz-receivers[r].iz)*(sources[s].iz-receivers[r].iz))) * dx;
                double curr_avg = 0;
                int path_len = 0;
                // Average velocity along source-receiver path (simplified ray)
                int steps = std::max(std::abs(sources[s].ix - receivers[r].ix), std::abs(sources[s].iz - receivers[r].iz));
                if (steps == 0) steps = 1;
                for (int k = 0; k <= steps; k++) {
                    int px = sources[s].ix + (receivers[r].ix - sources[s].ix) * k / steps;
                    int pz = sources[s].iz + (receivers[r].iz - sources[s].iz) * k / steps;
                    px = std::max(0, std::min(nx-1, px)); pz = std::max(0, std::min(nz-1, pz));
                    curr_avg += current_vel[pz][px];
                    path_len++;
                }
                curr_avg /= path_len;

                double synth_tt = dist / curr_avg * 1000.0;
                double true_tt = travel_times[s][r];
                double residual = synth_tt - true_tt;
                misfit += residual * residual;

                // Gradient: accumulate along ray path
                double grad_contrib = 2.0 * residual * (-dist / (curr_avg * curr_avg * path_len) * 1000.0);
                for (int k = 0; k <= steps; k++) {
                    int px = sources[s].ix + (receivers[r].ix - sources[s].ix) * k / steps;
                    int pz = sources[s].iz + (receivers[r].iz - sources[s].iz) * k / steps;
                    px = std::max(0, std::min(nx-1, px)); pz = std::max(0, std::min(nz-1, pz));
                    gradient[pz][px] += grad_contrib;
                    hessian_diag[pz][px] += grad_contrib * grad_contrib;
                }
            }
            total_adj++;
        }

        if (it == 0) initial_misfit = misfit;

        double grad_norm = 0, max_grad = 0;
        for (int iz = 0; iz < nz; iz++)
            for (int ix = 0; ix < nx; ix++) {
                grad_norm += gradient[iz][ix] * gradient[iz][ix];
                max_grad = std::max(max_grad, std::abs(gradient[iz][ix]));
            }
        grad_norm = std::sqrt(grad_norm);

        double step = step_init * std::pow(step_red, it);
        iter_results.push_back({it, misfit, grad_norm, max_grad, step});

        // Update velocity
        if (grad_norm > 0) {
            for (int iz = 0; iz < nz; iz++)
                for (int ix = 0; ix < nx; ix++)
                    current_vel[iz][ix] -= step * gradient[iz][ix] / grad_norm;
        }
    }

    // Compute velocity statistics
    double mean_vel = 0, min_vel = 1e9, max_vel = -1e9;
    for (int iz = 0; iz < nz; iz++)
        for (int ix = 0; ix < nx; ix++) {
            mean_vel += current_vel[iz][ix];
            min_vel = std::min(min_vel, current_vel[iz][ix]);
            max_vel = std::max(max_vel, current_vel[iz][ix]);
        }
    mean_vel /= (nx * nz);

    // Uncertainty: confidence = 1/(1+H_ii)
    double mean_unc = 0, max_unc = 0;
    std::vector<std::vector<double>> confidence(nz, std::vector<double>(nx));
    for (int iz = 0; iz < nz; iz++)
        for (int ix = 0; ix < nx; ix++) {
            double h = hessian_diag[iz][ix];
            confidence[iz][ix] = 1.0 / (1.0 + h);
            mean_unc += h;
            max_unc = std::max(max_unc, h);
        }
    mean_unc /= (nx * nz);

    double final_misfit = iter_results.back().misfit;
    double reduction = initial_misfit > 0 ? (1.0 - final_misfit / initial_misfit) * 100.0 : 0;
    bool converged = reduction > 0;

    // Write output
    std::ofstream out(output_path);
    out << std::fixed << std::setprecision(6);
    out << "{\n";

    // forward_modeling
    out << "  \"forward_modeling\": [\n";
    for (int s = 0; s < nsrc; s++) {
        out << "    {\"source_id\": \"" << sources[s].id << "\", \"ricker_wavelet\": [";
        for (int t = 0; t < nt; t++) { out << r6(src_wavelets[s][t]); if(t<nt-1) out << ", "; }
        out << "], \"max_amplitude\": " << r6(*std::max_element(src_wavelets[s].begin(), src_wavelets[s].end()));
        out << ", \"travel_times_us\": [";
        for (int r = 0; r < nrcv; r++) { out << r6(travel_times[s][r]); if(r<nrcv-1) out << ", "; }
        out << "]}" << (s<nsrc-1?",":"") << "\n";
    }
    out << "  ],\n";

    // attenuation_model
    out << "  \"attenuation_model\": [\n";
    for (size_t i = 0; i < atten_model.size(); i++) {
        auto& am = atten_model[i];
        out << "    {\"frequency_mhz\": " << r6(am.freq) << ", \"attenuation_coefficient\": " << r6(am.coeff);
        out << ", \"phase_velocity_correction\": " << r6(am.phase_corr) << "}";
        out << (i<atten_model.size()-1?",":"") << "\n";
    }
    out << "  ],\n";

    // gradient_computation
    out << "  \"gradient_computation\": [\n";
    for (size_t i = 0; i < iter_results.size(); i++) {
        auto& ir = iter_results[i];
        out << "    {\"iteration\": " << ir.iter << ", \"misfit_value\": " << r6(ir.misfit);
        out << ", \"gradient_norm\": " << r6(ir.grad_norm) << ", \"max_gradient\": " << r6(ir.max_grad);
        out << ", \"step_length\": " << r6(ir.step_len) << "}" << (i<iter_results.size()-1?",":"") << "\n";
    }
    out << "  ],\n";

    // velocity_reconstruction
    out << "  \"velocity_reconstruction\": {\"reconstructed_velocity\": [\n";
    for (int iz = 0; iz < nz; iz++) {
        out << "    ["; for (int ix = 0; ix < nx; ix++) { out << r6(current_vel[iz][ix]); if(ix<nx-1) out << ", "; }
        out << "]" << (iz<nz-1?",":"") << "\n";
    }
    out << "  ], \"mean_velocity_mps\": " << r6(mean_vel) << ", \"velocity_range\": [" << r6(min_vel) << ", " << r6(max_vel);
    out << "]},\n";

    // uncertainty_map
    out << "  \"uncertainty_map\": {\"diagonal_hessian\": [\n";
    for (int iz = 0; iz < nz; iz++) {
        out << "    ["; for (int ix = 0; ix < nx; ix++) { out << r6(hessian_diag[iz][ix]); if(ix<nx-1) out << ", "; }
        out << "]" << (iz<nz-1?",":"") << "\n";
    }
    out << "  ], \"mean_uncertainty\": " << r6(mean_unc) << ", \"max_uncertainty\": " << r6(max_unc);
    out << ", \"confidence_map\": [\n";
    for (int iz = 0; iz < nz; iz++) {
        out << "    ["; for (int ix = 0; ix < nx; ix++) { out << r6(confidence[iz][ix]); if(ix<nx-1) out << ", "; }
        out << "]" << (iz<nz-1?",":"") << "\n";
    }
    out << "  ]},\n";

    // inversion_summary
    out << "  \"inversion_summary\": {\"total_forward_solves\": " << total_fwd;
    out << ", \"total_adjoint_solves\": " << total_adj;
    out << ", \"final_misfit\": " << r6(final_misfit);
    out << ", \"misfit_reduction_percent\": " << r6(reduction);
    out << ", \"converged\": " << (converged?"true":"false");
    out << ", \"frequencies_used\": [";
    for (size_t i = 0; i < freq_list.size(); i++) { out << r6(freq_list[i]); if(i<freq_list.size()-1) out << ", "; }
    out << "]}\n}\n";
    out.close();
    std::cout << "FWI report generated: " << output_path << std::endl;
    return 0;
}
