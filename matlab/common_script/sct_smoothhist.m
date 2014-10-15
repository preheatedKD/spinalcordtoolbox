function sct_smoothhist(data,varargin)
% sct_smoothhist(nifti, ([xmin xmax], smoothness) )
if length(varargin)>1
    smoothness=varargin{2};
else
    smoothness=0.99;
end

data=data(:);
data(data==0)=[]; data(data==1)=[];
[n,xout] = hist(data,floor(length(data)/10));
if ~isempty(varargin)
    xout =  [varargin{1}(1) xout varargin{1}(2)];
    n=[0 n 0];
end
[fitresult, gof] = createFit(xout, n,smoothness);

% plot smooth hist
figure(43)
if ~isempty(varargin)
    xlim(varargin{1});
    xout=linspace(varargin{1}(1),varargin{1}(2),100);
end
n_smooth=feval(fitresult,xout);
area(xout,n_smooth)
% compute mean of the pdf
xmean=sum(n_smooth'.*xout)/sum(n_smooth);
disp(['mean: ' num2str(xmean)]) %int(f(x)*x)
% compute median of the pdf
[~,I] = min(abs(cumsum(n_smooth/sum(n_smooth))-0.5)); %int(f(x))=0.5
disp(['median: ' num2str(xout(I))])
disp(['std: ' num2str(sqrt(sum(n_smooth'.*(xout-xmean).^2/sum(n_smooth))))])



function [fitresult, gof] = createFit(xout, n,smoothness)
%CREATEFIT(XOUT,N)
%  Create a fit.
%
%  Data for 'untitled fit 1' fit:
%      X Input : xout
%      Y Output: n
%  Output:
%      fitresult : a fit object representing the fit.
%      gof : structure with goodness-of fit info.
%
%  See also FIT, CFIT, SFIT.

%  Auto-generated by MATLAB on 22-Apr-2014 20:05:47


%% Fit: 'untitled fit 1'.
[xData, yData] = prepareCurveData( xout, n );

% Set up fittype and options.
ft = fittype( 'smoothingspline' );
opts = fitoptions( ft );
opts.SmoothingParam = smoothness;

% Fit model to data.
[fitresult, gof] = fit( xData, yData, ft, opts );

% Plot fit with data.
figure(42);
h = plot( fitresult, xData, yData,'+');
legend( h, 'n vs. xout', 'nice histo', 'Location', 'NorthEast' );
set(h,'MarkerSize',20)
% Label axes
xlabel( 'xout' );
ylabel( 'n' );
grid on


