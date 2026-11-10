(() => {
const nav=navigate; navigate=function(v){nav(v);if(v==="studio")$("breadcrumb-current").textContent="AI Design Studio"};
let run=null,repo=null,token=null;
const role=s=>String(s||"").replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());
function render(d){
 const sec=$("studio-design-report");sec.replaceChildren();sec.classList.remove("hidden");
 const team=$("studio-agent-list");team.replaceChildren();const grid=el("div","report-grid");
 (d.results||[]).forEach(x=>{
  const row=el("div","studio-agent");row.append(el("span","studio-agent-dot","✓"));const info=el("div");info.append(el("b","",role(x.role)),el("small","",x.status||"completed"));row.append(info);team.append(row);
  const p=el("article","report-card");p.append(el("h3","",role(x.role)),el("p","summary-text",x.summary||""));
  if(x.decisions?.length){p.append(el("h4","","Decisions"));addList(p,x.decisions)}
  if(x.findings?.length){p.append(el("h4","","Findings"));addList(p,x.findings)}grid.append(p);
 });
 sec.append(el("h2","","Design team decisions"),grid,el("p","privacy-caption","AI recommendations are not implementation verification. Review the diff and run project checks before merging."));
}
async function json(url,body,options={}){const r=await fetch(url,{method:"POST",headers:apiHeaders(options),body:JSON.stringify(body)});const d=await r.json().catch(()=>({}));if(!r.ok){if(r.status===401||r.status===503)openSettings();throw Error(window.formatApiError?window.formatApiError(d.detail,"Request failed ("+r.status+")"):(typeof d.detail==="string"?d.detail:"Request failed ("+r.status+")"))}return d}
async function start(e){
 e.preventDefault();$("studio-error").textContent="";$("studio-proposal-error").textContent="";$("studio-implementation").classList.add("hidden");$("studio-design-report").classList.add("hidden");$("studio-proposal").classList.add("hidden");run=repo=token=null;
 const repository=$("studio-repository").value.trim(),brief=$("studio-brief").value.trim(),base=$("studio-base-branch").value.trim()||null,b=$("studio-submit");b.disabled=true;b.querySelector(".button-label").textContent="Coordinating specialist team…";
 try{
  [run,repo]=await Promise.all([json("/api/v1/design/runs",{brief,product_context:"Repository "+repository+"; base "+(base||"default")+"; design and implement the requested UI changes.",target_platforms:["web"],autonomy:"high"},{apiKey:true,llm:true}),json("/api/v1/repositories/inspect",{repository,ref:base,include_file_samples:false},{apiKey:true,llm:true,githubRead:true})]);
  render(run);$("studio-base-branch").value=repo.ref||base||"main";
  const paths=[...(repo.component_and_style_files||[]),...(repo.route_and_page_files||[]),...(repo.app_entry_points||[])].filter(p=>/\.(tsx|jsx|ts|js|vue|svelte|html|css|scss|less|dart|swift|kt|kts|qml|ui|m|mm|py|qss)$/i.test(p)).filter(p=>!/(^|\/)(api|auth|backend|database|infra|middleware|migrations|scripts|server|test|tests)(\/|$)/i.test(p));
  $("studio-files").value=[...new Set(paths)].slice(0,4).join(", ");$("studio-implementation").classList.remove("hidden");
  if(!paths.length)$("studio-proposal-error").textContent="No UI files detected. Enter up to four existing frontend source paths.";
  $("studio-implementation").scrollIntoView({behavior:"smooth",block:"start"});
 }catch(x){$("studio-error").textContent=x.message}finally{b.disabled=false;b.querySelector(".button-label").textContent="Start AI design session"}
}
async function propose(){
 $("studio-proposal-error").textContent="";
 if(!run||!repo){$("studio-proposal-error").textContent="Start a design session first.";return}
 if(!$("studio-source-consent").checked||!$("studio-confirm-files").checked){$("studio-proposal-error").textContent="Consent to source sharing and confirm the selected UI paths.";return}
 const files=$("studio-files").value.split(",").map(x=>x.trim()).filter(Boolean);if(!files.length||files.length>4){$("studio-proposal-error").textContent="Select one to four frontend files.";return}
 const b=$("studio-propose");b.disabled=true;b.textContent="Generating implementation diff…";
 try{
  const brief=$("studio-brief").value.trim(),context=(run.results||[]).map(x=>role(x.role)+": "+[x.summary,...(x.decisions||[]),...(x.findings||[])].filter(Boolean).join(" ")).join("\n").slice(0,10000);
  const d=await json("/api/v1/improvements/propose",{repository:repo.repository,ref:repo.ref,branch_name:$("studio-target-branch").value.trim()||null,design_brief:brief,target_files:files,findings:[{category:"design_brief",severity:"medium",title:"User-requested redesign",description:brief.slice(0,600),evidence:"User brief and specialist review.",recommendation:"Implement the requested direction in selected UI files while preserving behavior."}],visual_summary:context,source_sharing_consent:true},{apiKey:true,llm:true,githubRead:true});
  token=d.proposal_token;const p=$("studio-proposal");p.replaceChildren();p.classList.remove("hidden");p.append(el("h3","",d.summary),el("p","privacy-caption","Base: "+d.ref+" · Branch: "+d.branch_name+" · Files: "+d.files.map(x=>x.path).join(", ")+" · Expires in 30 minutes"),el("pre","proposal-diff",d.diff));
  const label=el("label","approval-check"),check=document.createElement("input");check.type="checkbox";label.append(check,el("span","","I reviewed this diff and approve creating the branch, pushing the changes, and opening a pull request."));p.append(label);
  const apply=el("button","primary-button","Approve, push branch and open PR →");apply.type="button";apply.disabled=true;check.onchange=()=>apply.disabled=!check.checked;
  apply.onclick=async()=>{if(!check.checked||!token)return;apply.disabled=true;apply.textContent="Pushing approved changes…";try{const out=await json("/api/v1/improvements/apply",{proposal_token:token,approval:true},{apiKey:true,githubWrite:true});p.append(el("p","studio-success","Pushed to "+out.branch+" · Pull request #"+out.number));const a=el("a","proposal-link","Open pull request →");a.href=out.pull_request_url;a.target="_blank";a.rel="noreferrer";p.append(a);token=null}catch(x){$("studio-proposal-error").textContent=x.message;apply.disabled=false;apply.textContent="Retry approved push →"}};
  p.append(apply);p.scrollIntoView({behavior:"smooth",block:"start"});
 }catch(x){$("studio-proposal-error").textContent=x.message}finally{b.disabled=false;b.textContent="Generate code proposal →"}
}
$("studio-form").addEventListener("submit",start);$("studio-propose").addEventListener("click",propose);if(location.hash==="#studio"||window.__disInitialHash==="#studio")navigate("studio");
})();